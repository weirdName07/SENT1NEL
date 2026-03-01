"""First-class event layer — typed events for anomalies, geofence, lifecycle, tracks."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

import orjson
from pydantic import BaseModel, Field

from sentinel.core.schemas import EntityType, Position


class EventType(str, Enum):
    # Geopolitics
    GEOPOLITICAL_NEWS = "geopolitics.news"

    # Anomaly
    ANOMALY_DETECTED = "anomaly.detected"

    # Geofence
    GEOFENCE_ENTER = "geofence.enter"
    GEOFENCE_EXIT = "geofence.exit"
    GEOFENCE_DWELL = "geofence.dwell"

    # Lifecycle
    LIFECYCLE_TRANSITION = "lifecycle.transition"

    # Track
    TRACK_CREATED = "track.created"
    TRACK_LOST = "track.lost"
    TRACK_MERGED = "track.merged"
    TRACK_REACQUIRED = "track.reacquired"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SentinelEvent(BaseModel):
    """
    Discrete intelligence event.

    Events are the unit of intelligence output. Every anomaly detection,
    geofence violation, lifecycle transition, and track management action
    produces an event that flows through NATS and is persisted independently.
    """

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Source entity (may be None for system-level events)
    entity_id: Optional[UUID] = None
    entity_type: Optional[EntityType] = None
    source_id: Optional[str] = None
    track_id: Optional[UUID] = None

    # Event payload
    severity: Severity = Severity.LOW
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str = ""
    position: Optional[Position] = None

    # Context
    metadata: dict = Field(default_factory=dict)

    # Observability
    trace_id: Optional[str] = None

    def serialize(self) -> bytes:
        """Serialize for NATS publishing."""
        return orjson.dumps(self.model_dump(), default=_json_default)

    @classmethod
    def deserialize(cls, data: bytes) -> SentinelEvent:
        return cls.model_validate(orjson.loads(data))

    @property
    def nats_subject(self) -> str:
        """Derive NATS subject from event type: sentinel.events.anomaly, etc."""
        category = self.event_type.value.split(".")[0]
        return f"sentinel.events.{category}"


def _json_default(obj: object) -> object:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Cannot serialize {type(obj)}")
