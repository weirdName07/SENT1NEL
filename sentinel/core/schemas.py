"""Unified entity schemas — v2 with lifecycle, trace IDs, and observation counts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

import orjson
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────

class EntityType(str, Enum):
    AIRCRAFT = "aircraft"
    VESSEL = "vessel"
    SATELLITE = "satellite"
    EARTHQUAKE = "earthquake"
    WEATHER = "weather"


class EntityLifecycle(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    STALE = "stale"
    LOST = "lost"
    ARCHIVED = "archived"


# ── Value Objects ─────────────────────────────────────────────

class Position(BaseModel):
    """WGS84 geographic position."""

    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    accuracy_m: Optional[float] = None

    def to_wkt(self) -> str:
        """Convert to WKT for PostGIS."""
        if self.altitude_m is not None:
            return f"SRID=4326;POINTZ({self.longitude} {self.latitude} {self.altitude_m})"
        return f"SRID=4326;POINT({self.longitude} {self.latitude})"


class Velocity(BaseModel):
    """Kinematic velocity vector."""

    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    vertical_rate_mps: Optional[float] = None


# ── Core Entity State ────────────────────────────────────────

class EntityState(BaseModel):
    """
    Unified entity representation.

    Every observation — aircraft position, vessel report, earthquake event —
    is normalized into this schema before storage and processing.
    """

    entity_id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    source_id: str          # Original identifier (ICAO24, MMSI, NORAD ID)
    source: str             # Data source name ("opensky", "aisstream", etc.)

    # Spatial-temporal core
    position: Position
    velocity: Optional[Velocity] = None
    timestamp: datetime     # Observation time (source clock)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Lifecycle
    lifecycle: EntityLifecycle = EntityLifecycle.NEW
    last_transition_at: Optional[datetime] = None

    # Intelligence fields
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    risk_score: Optional[float] = Field(ge=0.0, le=1.0, default=None)

    # Track management
    track_id: Optional[UUID] = None
    observation_count: int = 0

    # Extensible metadata
    metadata: dict = Field(default_factory=dict)

    # Anomaly flags (populated by analytics layer)
    anomalies: list[str] = Field(default_factory=list)

    # Observability
    trace_id: Optional[str] = None

    def serialize(self) -> bytes:
        """Fast serialization via orjson."""
        return orjson.dumps(self.model_dump(), default=_json_default)

    @classmethod
    def deserialize(cls, data: bytes) -> EntityState:
        """Deserialize from bytes."""
        return cls.model_validate(orjson.loads(data))

    @property
    def entity_key(self) -> str:
        """Unique key for Redis/dedup: source_id + entity_type."""
        return f"{self.source_id}:{self.entity_type.value}"


def _json_default(obj: object) -> object:
    """Handle UUID, datetime serialization for orjson."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Cannot serialize {type(obj)}")
