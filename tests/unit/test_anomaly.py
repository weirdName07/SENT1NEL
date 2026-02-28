"""Unit tests for anomaly detection."""

from datetime import datetime, timezone

from sentinel.analytics.anomaly import AnomalyDetector
from sentinel.core.schemas import EntityState, EntityType, Position, Velocity


class TestAnomalyDetector:
    def setup_method(self):
        self.detector = AnomalyDetector()

    def _make_entity(
        self, entity_type: EntityType, speed: float, lat: float = 40.0, lon: float = -74.0,
        alt: float = 10000, heading: float = 90.0, source_id: str = "test1"
    ) -> EntityState:
        return EntityState(
            entity_type=entity_type,
            source_id=source_id,
            source="test",
            position=Position(latitude=lat, longitude=lon, altitude_m=alt),
            velocity=Velocity(speed_mps=speed, heading_deg=heading),
            timestamp=datetime.now(timezone.utc),
        )

    def test_normal_aircraft_no_anomaly(self):
        entity = self._make_entity(EntityType.AIRCRAFT, speed=220)
        events = self.detector.check(entity)
        assert len(events) == 0

    def test_fast_aircraft_speed_anomaly(self):
        # 500 m/s — way above max (340)
        entity = self._make_entity(EntityType.AIRCRAFT, speed=500)
        events = self.detector.check(entity)
        assert len(events) > 0
        assert any("SPEED" in e.reason for e in events)

    def test_normal_vessel_no_anomaly(self):
        entity = self._make_entity(EntityType.VESSEL, speed=5.0, alt=0)
        events = self.detector.check(entity)
        assert len(events) == 0

    def test_fast_vessel_anomaly(self):
        # 30 m/s — above vessel max (25)
        entity = self._make_entity(EntityType.VESSEL, speed=30.0, alt=0)
        events = self.detector.check(entity)
        assert len(events) > 0

    def test_position_teleport(self):
        # First observation
        e1 = self._make_entity(EntityType.AIRCRAFT, speed=220, lat=40.0, lon=-74.0)
        self.detector.check(e1)

        # Second observation — teleported 200km
        e2 = self._make_entity(EntityType.AIRCRAFT, speed=220, lat=42.0, lon=-74.0)
        events = self.detector.check(e2)
        assert any("TELEPORT" in e.reason for e in events)

    def test_heading_reversal(self):
        e1 = self._make_entity(EntityType.AIRCRAFT, speed=220, heading=90)
        self.detector.check(e1)

        e2 = self._make_entity(EntityType.AIRCRAFT, speed=220, heading=270)
        events = self.detector.check(e2)
        assert any("HEADING" in e.reason for e in events)

    def test_earthquake_skipped(self):
        entity = EntityState(
            entity_type=EntityType.EARTHQUAKE,
            source_id="eq1",
            source="usgs",
            position=Position(latitude=35.0, longitude=139.0),
            timestamp=datetime.now(timezone.utc),
        )
        events = self.detector.check(entity)
        assert len(events) == 0
