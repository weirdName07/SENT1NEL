"""Unit tests for core schemas."""

from datetime import datetime, timezone
from uuid import UUID

from sentinel.core.schemas import (
    EntityLifecycle,
    EntityState,
    EntityType,
    Position,
    Velocity,
)


class TestPosition:
    def test_to_wkt_2d(self):
        p = Position(latitude=40.7128, longitude=-74.0060)
        wkt = p.to_wkt()
        assert wkt.startswith("SRID=4326;POINT(")
        assert "-74.006" in wkt
        assert "40.7128" in wkt

    def test_to_wkt_3d(self):
        p = Position(latitude=40.7128, longitude=-74.0060, altitude_m=10000)
        wkt = p.to_wkt()
        assert wkt.startswith("SRID=4326;POINTZ(")
        assert "-74.006" in wkt
        assert "40.7128" in wkt
        assert "10000" in wkt


class TestEntityState:
    def test_create_aircraft(self):
        entity = EntityState(
            entity_type=EntityType.AIRCRAFT,
            source_id="a1b2c3",
            source="opensky",
            position=Position(latitude=40.7128, longitude=-74.0060, altitude_m=10000),
            velocity=Velocity(speed_mps=250, heading_deg=90),
            timestamp=datetime.now(timezone.utc),
        )
        assert entity.entity_type == EntityType.AIRCRAFT
        assert entity.lifecycle == EntityLifecycle.NEW
        assert entity.confidence == 0.5
        assert isinstance(entity.entity_id, UUID)

    def test_entity_key(self):
        entity = EntityState(
            entity_type=EntityType.VESSEL,
            source_id="123456789",
            source="aisstream",
            position=Position(latitude=0, longitude=0),
            timestamp=datetime.now(timezone.utc),
        )
        assert entity.entity_key == "123456789:vessel"

    def test_serialize_roundtrip(self):
        entity = EntityState(
            entity_type=EntityType.AIRCRAFT,
            source_id="ab12cd",
            source="opensky",
            position=Position(latitude=51.5074, longitude=-0.1278, altitude_m=5000),
            velocity=Velocity(speed_mps=200, heading_deg=270, vertical_rate_mps=-5),
            timestamp=datetime.now(timezone.utc),
            metadata={"callsign": "BAW123"},
        )
        data = entity.serialize()
        restored = EntityState.deserialize(data)
        assert restored.source_id == entity.source_id
        assert restored.entity_type == entity.entity_type
        assert restored.position.latitude == entity.position.latitude
        assert restored.metadata["callsign"] == "BAW123"

    def test_confidence_bounds(self):
        entity = EntityState(
            entity_type=EntityType.EARTHQUAKE,
            source_id="eq1",
            source="usgs",
            position=Position(latitude=0, longitude=0),
            timestamp=datetime.now(timezone.utc),
            confidence=0.95,
        )
        assert 0 <= entity.confidence <= 1.0
