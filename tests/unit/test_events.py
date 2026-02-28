"""Unit tests for event schema."""

from sentinel.core.events import EventType, SentinelEvent, Severity
from sentinel.core.schemas import EntityType, Position


class TestSentinelEvent:
    def test_create_anomaly_event(self):
        event = SentinelEvent(
            event_type=EventType.ANOMALY_DETECTED,
            entity_type=EntityType.AIRCRAFT,
            source_id="a1b2c3",
            severity=Severity.HIGH,
            confidence=0.87,
            reason="Altitude deviation > 4σ",
            position=Position(latitude=40.7, longitude=-74.0),
        )
        assert event.event_type == EventType.ANOMALY_DETECTED
        assert event.severity == Severity.HIGH
        assert event.nats_subject == "sentinel.events.anomaly"

    def test_nats_subject_routing(self):
        cases = [
            (EventType.ANOMALY_DETECTED, "sentinel.events.anomaly"),
            (EventType.GEOFENCE_ENTER, "sentinel.events.geofence"),
            (EventType.LIFECYCLE_TRANSITION, "sentinel.events.lifecycle"),
            (EventType.TRACK_CREATED, "sentinel.events.track"),
        ]
        for event_type, expected_subject in cases:
            event = SentinelEvent(event_type=event_type)
            assert event.nats_subject == expected_subject

    def test_serialize_roundtrip(self):
        event = SentinelEvent(
            event_type=EventType.GEOFENCE_EXIT,
            source_id="vessel_123",
            severity=Severity.MEDIUM,
            reason="Left restricted zone",
            metadata={"geofence_name": "Port Authority"},
        )
        data = event.serialize()
        restored = SentinelEvent.deserialize(data)
        assert restored.event_type == event.event_type
        assert restored.reason == event.reason
        assert restored.metadata["geofence_name"] == "Port Authority"
