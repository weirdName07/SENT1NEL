"""Normalizer — transforms raw source-specific data into unified EntityState."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog

from sentinel.core.schemas import EntityState, EntityType, Position, Velocity

log = structlog.get_logger()


class Normalizer:
    """
    Converts raw ingestion dicts (from each connector) into unified EntityState.

    Each source has a slightly different raw format; the normalizer handles
    the mapping to Position, Velocity, and metadata fields.
    """

    def normalize(self, raw: dict) -> EntityState | None:
        source = "unknown"
        try:
            if isinstance(raw, dict):
                source = raw.get("source", "unknown")
            if source == "opensky":
                return self._normalize_opensky(raw)
            elif source == "synthetic_flights":
                return self._normalize_synthetic(raw)
            elif source == "usgs":
                return self._normalize_usgs(raw)
            elif source == "celestrak":
                return self._normalize_celestrak(raw)
            elif source == "aisstream":
                return self._normalize_aisstream(raw)
            elif source == "openmeteo":
                return self._normalize_openmeteo(raw)
            else:
                log.warning("normalizer.unknown_source", source=source)
                return None
        except Exception:
            log.exception("normalizer.error", source=source)
            return None

    def _normalize_synthetic(self, raw: dict) -> EntityState:
        ts = raw.get("timestamp", 0)
        return EntityState(
            entity_id=uuid4(),
            entity_type=EntityType.AIRCRAFT,
            source_id=raw["source_id"],
            source="synthetic_flights",
            position=Position(
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                altitude_m=raw.get("altitude_m"),
            ),
            velocity=Velocity(
                speed_mps=raw.get("velocity_mps"),
                heading_deg=raw.get("heading"),
                vertical_rate_mps=0.0,
            ),
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
            metadata={
                "callsign": raw.get("callsign", ""),
                "airline": raw.get("airline", ""),
                "origin": raw.get("origin", ""),
                "destination": raw.get("destination", ""),
            },
            trace_id=f"syn-{raw['source_id']}-{uuid4().hex[:8]}",
        )

    def _normalize_opensky(self, raw: dict) -> EntityState:
        ts = raw.get("timestamp", 0)
        return EntityState(
            entity_id=uuid4(),
            entity_type=EntityType.AIRCRAFT,
            source_id=raw["source_id"],
            source="opensky",
            position=Position(
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                altitude_m=raw.get("altitude_m"),
            ),
            velocity=Velocity(
                speed_mps=raw.get("speed_mps"),
                heading_deg=raw.get("heading_deg"),
                vertical_rate_mps=raw.get("vertical_rate_mps"),
            ),
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
            metadata={
                "callsign": raw.get("callsign", ""),
                "origin_country": raw.get("origin_country", ""),
                "on_ground": raw.get("on_ground", False),
                "squawk": raw.get("squawk"),
            },
            trace_id=f"osky-{raw['source_id']}-{uuid4().hex[:8]}",
        )

    def _normalize_usgs(self, raw: dict) -> EntityState:
        ts = raw.get("timestamp", 0)
        return EntityState(
            entity_id=uuid4(),
            entity_type=EntityType.EARTHQUAKE,
            source_id=raw["source_id"],
            source="usgs",
            position=Position(
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                altitude_m=raw.get("altitude_m"),
            ),
            velocity=None,
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
            confidence=0.9,  # USGS data is authoritative
            metadata={
                "magnitude": raw.get("magnitude"),
                "place": raw.get("place"),
                "felt": raw.get("felt"),
                "significance": raw.get("significance"),
                "tsunami": raw.get("tsunami"),
                "alert": raw.get("alert"),
                "mag_type": raw.get("mag_type"),
            },
            trace_id=f"usgs-{raw['source_id']}",
        )

    def _normalize_celestrak(self, raw: dict) -> EntityState:
        ts = raw.get("timestamp", 0)
        return EntityState(
            entity_id=uuid4(),
            entity_type=EntityType.SATELLITE,
            source_id=raw["source_id"],
            source="celestrak",
            position=Position(
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                altitude_m=raw.get("altitude_m"),
            ),
            velocity=Velocity(
                speed_mps=raw.get("speed_mps"),
            ),
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
            confidence=0.7,  # Propagated, not directly observed
            metadata={
                "name": raw.get("name", ""),
                "norad_id": raw.get("norad_id", ""),
                "tle_epoch": raw.get("tle_epoch"),
            },
            trace_id=f"ctrk-{raw['source_id']}-{uuid4().hex[:8]}",
        )

    def _normalize_aisstream(self, raw: dict) -> EntityState:
        return EntityState(
            entity_id=uuid4(),
            entity_type=EntityType.VESSEL,
            source_id=raw["source_id"],
            source="aisstream",
            position=Position(
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                altitude_m=0,
            ),
            velocity=Velocity(
                speed_mps=raw.get("speed_mps"),
                heading_deg=raw.get("heading_deg"),
            ),
            timestamp=datetime.now(timezone.utc),
            metadata={
                "name": raw.get("name", ""),
                "mmsi": raw.get("mmsi", ""),
                "ship_type": raw.get("ship_type"),
                "nav_status": raw.get("nav_status"),
                "cog": raw.get("cog"),
            },
            trace_id=f"ais-{raw['source_id']}-{uuid4().hex[:8]}",
        )

    def _normalize_openmeteo(self, raw: dict) -> EntityState:
        ts = raw.get("timestamp", 0)
        return EntityState(
            entity_id=uuid4(),
            entity_type=EntityType.WEATHER,
            source_id=raw["source_id"],
            source="openmeteo",
            position=Position(
                latitude=raw["latitude"],
                longitude=raw["longitude"],
                altitude_m=raw.get("altitude_m"),
            ),
            velocity=Velocity(
                speed_mps=raw.get("wind_speed_mps"),
                heading_deg=raw.get("wind_direction_deg"),
            ) if raw.get("wind_speed_mps") else None,
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc),
            confidence=0.85,
            metadata={
                "temperature_c": raw.get("temperature_c"),
                "humidity_pct": raw.get("humidity_pct"),
                "precipitation_mm": raw.get("precipitation_mm"),
                "weather_code": raw.get("weather_code"),
                "location_name": raw.get("location_name"),
            },
            trace_id=f"wx-{raw['source_id']}",
        )
