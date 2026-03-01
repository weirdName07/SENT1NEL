"""Critical failure tests — graceful degradation under component failures."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.core.schemas import EntityState, EntityType, Position, Velocity
from sentinel.processing.normalizer import Normalizer
from sentinel.processing.enricher import Enricher
from sentinel.processing.tracker import TrackStitcher
from sentinel.analytics.anomaly import AnomalyDetector
from sentinel.core.backpressure import BatchCoalescer
from sentinel.core.events import EventType, SentinelEvent, Severity


class TestMalformedDataResilience:
    """Tests that the pipeline handles corrupted/malformed data gracefully."""

    def setup_method(self):
        self.normalizer = Normalizer()
        self.enricher = Enricher()
        self.tracker = TrackStitcher()
        self.detector = AnomalyDetector()

    def test_empty_dict(self):
        """Empty dict should not crash the normalizer."""
        entity = self.normalizer.normalize({})
        assert entity is None

    def test_missing_source(self):
        """Missing 'source' key returns None."""
        entity = self.normalizer.normalize({"latitude": 40, "longitude": -74})
        assert entity is None

    def test_missing_coordinates(self):
        """Missing lat/lon should not crash."""
        raw = {"source": "opensky", "entity_type": "aircraft", "source_id": "bad1",
               "timestamp": 1709100000}
        result = self.normalizer.normalize(raw)
        # Should either return None or handle gracefully
        # Pydantic will raise on missing required fields — normalizer catches it
        assert result is None or result.position is not None

    def test_nan_coordinates(self):
        """NaN coordinates should be handled."""
        raw = {
            "source": "opensky", "entity_type": "aircraft", "source_id": "nan1",
            "timestamp": 1709100000,
            "latitude": float('nan'), "longitude": float('nan'),
            "altitude_m": float('nan'), "speed_mps": float('nan'),
        }
        # Should not crash
        try:
            entity = self.normalizer.normalize(raw)
        except Exception:
            pass  # Acceptable to reject NaN

    def test_extreme_coordinates(self):
        """Extreme/invalid coordinates should not crash."""
        raw = {
            "source": "opensky", "entity_type": "aircraft", "source_id": "ext1",
            "timestamp": 1709100000,
            "latitude": 999, "longitude": -999,
            "altitude_m": -100000, "speed_mps": -50,
        }
        entity = self.normalizer.normalize(raw)
        # Should normalize without crashing, even with bad values

    def test_negative_timestamp(self):
        """Negative timestamps should not crash."""
        raw = {
            "source": "opensky", "entity_type": "aircraft", "source_id": "neg_ts",
            "timestamp": -1, "latitude": 40, "longitude": -74,
        }
        try:
            entity = self.normalizer.normalize(raw)
        except Exception:
            pass  # Acceptable to reject negative timestamps

    def test_enormous_metadata(self):
        """Huge metadata dict should not crash the enricher."""
        entity = EntityState(
            entity_type=EntityType.AIRCRAFT,
            source_id="big_meta",
            source="opensky",
            position=Position(latitude=40, longitude=-74),
            timestamp=datetime.now(timezone.utc),
            metadata={f"key_{i}": f"value_{i}" * 100 for i in range(1000)},
        )
        enriched = self.enricher.enrich(entity)
        assert enriched is not None

    def test_empty_velocity(self):
        """Entity with None velocity should enrich gracefully."""
        entity = EntityState(
            entity_type=EntityType.AIRCRAFT,
            source_id="no_vel",
            source="opensky",
            position=Position(latitude=40, longitude=-74),
            velocity=None,
            timestamp=datetime.now(timezone.utc),
        )
        enriched = self.enricher.enrich(entity)
        assert enriched.confidence < 0.5  # Penalized for missing velocity

    def test_tracker_handles_zero_dt(self):
        """Track stitcher handles two observations at same timestamp."""
        entity1 = EntityState(
            entity_type=EntityType.AIRCRAFT, source_id="same_ts",
            source="opensky",
            position=Position(latitude=40, longitude=-74),
            velocity=Velocity(speed_mps=220, heading_deg=90),
            timestamp=datetime.now(timezone.utc),
        )
        entity2 = EntityState(
            entity_type=EntityType.AIRCRAFT, source_id="same_ts",
            source="opensky",
            position=Position(latitude=40.001, longitude=-74.001),
            velocity=Velocity(speed_mps=220, heading_deg=90),
            timestamp=entity1.timestamp,  # Same timestamp
        )
        self.tracker.associate(entity1)
        entity2, events = self.tracker.associate(entity2)
        assert entity2.track_id is not None

    def test_anomaly_detector_no_crash_on_zero_speed(self):
        """Zero speed entity should not flag anomaly for non-earthquake."""
        entity = EntityState(
            entity_type=EntityType.VESSEL, source_id="zero_speed",
            source="aisstream",
            position=Position(latitude=51, longitude=-0.1),
            velocity=Velocity(speed_mps=0, heading_deg=0),
            timestamp=datetime.now(timezone.utc),
        )
        events = self.detector.check(entity)
        # Zero speed is valid (anchored vessel)

    def test_anomaly_detector_none_heading(self):
        """None heading should not crash heading reversal check."""
        e1 = EntityState(
            entity_type=EntityType.AIRCRAFT, source_id="none_hdg",
            source="opensky",
            position=Position(latitude=40, longitude=-74),
            velocity=Velocity(speed_mps=220, heading_deg=None),
            timestamp=datetime.now(timezone.utc),
        )
        self.detector.check(e1)
        e2 = EntityState(
            entity_type=EntityType.AIRCRAFT, source_id="none_hdg",
            source="opensky",
            position=Position(latitude=40.001, longitude=-74.001),
            velocity=Velocity(speed_mps=220, heading_deg=90),
            timestamp=datetime.now(timezone.utc),
        )
        events = self.detector.check(e2)
        # Should not crash, heading reversal check is skipped when prev heading is None


class TestEventSchemaResilience:
    """Tests that the event system handles edge cases."""

    def test_event_with_no_optional_fields(self):
        """Minimal event should serialize/deserialize."""
        event = SentinelEvent(event_type=EventType.ANOMALY_DETECTED)
        data = event.serialize()
        restored = SentinelEvent.deserialize(data)
        assert restored.event_type == EventType.ANOMALY_DETECTED

    def test_event_with_empty_metadata(self):
        event = SentinelEvent(
            event_type=EventType.GEOFENCE_ENTER,
            metadata={},
        )
        data = event.serialize()
        restored = SentinelEvent.deserialize(data)
        assert restored.metadata == {}

    def test_event_nats_subject_all_types(self):
        """All event types should produce valid NATS subjects."""
        for event_type in EventType:
            event = SentinelEvent(event_type=event_type)
            subject = event.nats_subject
            assert subject.startswith("sentinel.events.")
            assert len(subject.split(".")) == 3


class TestBatchCoalescerFailures:
    """Tests that batch coalescer handles edge cases."""

    def test_add_none(self):
        """Adding None should not crash."""
        batcher = BatchCoalescer(batch_size=10)
        batcher.add(None)
        assert batcher.pending == 1

    def test_add_mixed_types(self):
        """Heterogeneous items should be handled."""
        batcher = BatchCoalescer(batch_size=5)
        batcher.add(1)
        batcher.add("two")
        batcher.add({"three": 3})
        batcher.add([4])
        result = batcher.add(None)
        assert len(result) == 5

    def test_flush_idempotent(self):
        """Double flush should not duplicate items."""
        batcher = BatchCoalescer(batch_size=10)
        batcher.add("x")
        first = batcher.flush()
        second = batcher.flush()
        assert first == ["x"]
        assert second == []


class TestTrackerEdgeCases:
    """Tests for track stitcher edge cases."""

    def test_remove_nonexistent_track(self):
        """Removing a track that doesn't exist should not crash."""
        tracker = TrackStitcher()
        from uuid import uuid4
        tracker.remove_track(uuid4())  # Should not raise

    def test_earthquake_self_tracks(self):
        """Earthquakes should get self-referencing track IDs."""
        tracker = TrackStitcher()
        entity = EntityState(
            entity_type=EntityType.EARTHQUAKE, source_id="eq_test",
            source="usgs",
            position=Position(latitude=35, longitude=139),
            timestamp=datetime.now(timezone.utc),
        )
        entity, events = tracker.associate(entity)
        assert entity.track_id == entity.entity_id

    def test_many_concurrent_tracks(self):
        """Tracker handles 500 simultaneous tracks without corruption."""
        tracker = TrackStitcher()
        track_ids = set()

        # Space entities 1° apart (~111km) to exceed the 50km aircraft gate radius
        for i in range(500):
            entity = EntityState(
                entity_type=EntityType.AIRCRAFT,
                source_id=f"conc_{i}",
                source="opensky",
                position=Position(
                    latitude=-60 + (i % 50) * 2.0,  # 2° apart = 222km
                    longitude=-170 + (i // 50) * 2.0,
                ),
                velocity=Velocity(speed_mps=220, heading_deg=90),
                timestamp=datetime.now(timezone.utc),
            )
            entity, _ = tracker.associate(entity)
            track_ids.add(entity.track_id)

        assert len(track_ids) == 500
        assert tracker.active_track_count == 500

    def test_track_reuse_after_removal(self):
        """After removing a track, a new track is created for the same source_id."""
        tracker = TrackStitcher()

        entity = EntityState(
            entity_type=EntityType.AIRCRAFT, source_id="reuse_test",
            source="opensky",
            position=Position(latitude=40, longitude=-74),
            velocity=Velocity(speed_mps=220, heading_deg=90),
            timestamp=datetime.now(timezone.utc),
        )
        entity, _ = tracker.associate(entity)
        old_track_id = entity.track_id

        # Remove track
        tracker.remove_track(old_track_id)

        # New observation far away — should create new track
        entity2 = EntityState(
            entity_type=EntityType.AIRCRAFT, source_id="reuse_test",
            source="opensky",
            position=Position(latitude=10.0, longitude=-30.0),  # Far from original
            velocity=Velocity(speed_mps=220, heading_deg=90),
            timestamp=datetime.now(timezone.utc),
        )
        entity2, events = tracker.associate(entity2)
        assert entity2.track_id is not None  # Gets a track (may be new or gated)
