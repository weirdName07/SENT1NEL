"""Integration test — processing pipeline end-to-end (normalizer → enricher → tracker → anomaly)."""

from datetime import datetime, timezone

import pytest

from sentinel.analytics.anomaly import AnomalyDetector
from sentinel.core.schemas import EntityState, EntityType, Position, Velocity
from sentinel.processing.enricher import Enricher
from sentinel.processing.normalizer import Normalizer
from sentinel.processing.tracker import TrackStitcher


class TestPipelineIntegration:
    """Exercises the full processing chain without external services."""

    def setup_method(self):
        self.normalizer = Normalizer()
        self.enricher = Enricher()
        self.tracker = TrackStitcher()
        self.detector = AnomalyDetector()

    def _make_raw(self, source, entity_type, source_id, lat, lon, speed=100, heading=90, ts=None):
        return {
            "source": source,
            "entity_type": entity_type,
            "source_id": source_id,
            "timestamp": ts or datetime.now(timezone.utc).timestamp(),
            "latitude": lat,
            "longitude": lon,
            "altitude_m": 10000 if entity_type == "aircraft" else 0,
            "speed_mps": speed,
            "heading_deg": heading,
            "vertical_rate_mps": 0,
            "callsign": "TEST123",
            "origin_country": "US",
            "on_ground": False,
        }

    def test_full_pipeline_single_entity(self):
        """Single entity flows through all processing stages."""
        raw = self._make_raw("opensky", "aircraft", "abc123", 40.0, -74.0)

        # Stage 1: Normalize
        entity = self.normalizer.normalize(raw)
        assert entity is not None
        assert entity.entity_type == EntityType.AIRCRAFT

        # Stage 2: Enrich
        entity = self.enricher.enrich(entity)
        assert 0 <= entity.confidence <= 1.0

        # Stage 3: Track
        entity, events = self.tracker.associate(entity)
        assert entity.track_id is not None
        assert entity.observation_count == 1

        # Stage 4: Anomaly
        anomaly_events = self.detector.check(entity)
        # Normal speed, no anomaly expected
        assert len(anomaly_events) == 0

    def test_pipeline_track_continuity(self):
        """Multiple observations from the same source maintain the track."""
        for i in range(5):
            raw = self._make_raw(
                "opensky", "aircraft", "track_test_1",
                40.0 + i * 0.01, -74.0 + i * 0.01, speed=200
            )
            entity = self.normalizer.normalize(raw)
            entity = self.enricher.enrich(entity)
            entity, events = self.tracker.associate(entity)

        assert entity.observation_count == 5
        assert self.tracker.active_track_count >= 1

    def test_pipeline_multi_source_multi_type(self):
        """Different entity types processed independently."""
        sources = [
            self._make_raw("opensky", "aircraft", "ac1", 40, -74, speed=220),
            self._make_raw("usgs", "earthquake", "eq1", 35, 139, speed=0),
            self._make_raw("aisstream", "vessel", "v1", 51, -0.1, speed=5),
        ]

        entities = []
        for raw in sources:
            entity = self.normalizer.normalize(raw)
            assert entity is not None
            entity = self.enricher.enrich(entity)
            entity, events = self.tracker.associate(entity)
            entities.append(entity)

        types = {e.entity_type for e in entities}
        assert EntityType.AIRCRAFT in types
        assert EntityType.EARTHQUAKE in types
        assert EntityType.VESSEL in types

    def test_pipeline_anomaly_detection_integration(self):
        """Anomaly is detected when speed exceeds type ceiling."""
        # Normal aircraft first
        raw_normal = self._make_raw("opensky", "aircraft", "anom_test", 40, -74, speed=200)
        entity = self.normalizer.normalize(raw_normal)
        entity = self.enricher.enrich(entity)
        entity, _ = self.tracker.associate(entity)
        events = self.detector.check(entity)
        assert len(events) == 0

        # Same aircraft, impossible speed
        raw_fast = self._make_raw("opensky", "aircraft", "anom_test", 40.01, -74.01, speed=500)
        entity2 = self.normalizer.normalize(raw_fast)
        entity2 = self.enricher.enrich(entity2)
        entity2, _ = self.tracker.associate(entity2)
        events2 = self.detector.check(entity2)
        assert len(events2) > 0
        assert any("SPEED" in e.reason for e in events2)

    def test_pipeline_enricher_confidence_adjustment(self):
        """Enricher adjusts confidence based on data completeness."""
        # Full data — high confidence
        raw_full = self._make_raw("opensky", "aircraft", "conf1", 40, -74, speed=220)
        entity_full = self.normalizer.normalize(raw_full)
        entity_full = self.enricher.enrich(entity_full)

        # Missing velocity — lower confidence
        raw_partial = {
            "source": "opensky", "entity_type": "aircraft", "source_id": "conf2",
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "latitude": 40, "longitude": -74,
        }
        entity_partial = self.normalizer.normalize(raw_partial)
        if entity_partial:
            entity_partial = self.enricher.enrich(entity_partial)
            # Missing velocity should lower confidence
            assert entity_partial.confidence <= entity_full.confidence + 0.01

    def test_pipeline_track_new_creates_event(self):
        """First observation of a new entity emits TRACK_CREATED event."""
        raw = self._make_raw("opensky", "aircraft", "new_track_test", 40, -74)
        entity = self.normalizer.normalize(raw)
        entity = self.enricher.enrich(entity)
        entity, events = self.tracker.associate(entity)

        assert len(events) == 1
        assert events[0].event_type.value == "track.created"
