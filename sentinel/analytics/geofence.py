"""Geofencing engine — PostGIS-backed enter/exit/dwell detection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from sentinel.core.events import EventType, SentinelEvent, Severity
from sentinel.core.schemas import EntityState, Position
from sentinel.storage.timescale import TimescaleStore

log = structlog.get_logger()


class GeofenceEngine:
    """
    Geofence engine using PostGIS spatial queries.

    Checks each entity position against active geofence zones.
    Emits GEOFENCE_ENTER, GEOFENCE_EXIT, and GEOFENCE_DWELL events.
    """

    def __init__(self, db: TimescaleStore) -> None:
        self._db = db
        # entity_key → set of geofence_ids currently inside
        self._inside: dict[str, set[str]] = {}

    async def check(self, entity: EntityState) -> list[SentinelEvent]:
        """Check entity position against all active geofences."""
        events: list[SentinelEvent] = []
        entity_key = entity.entity_key

        # Query geofences containing this point
        current_fences = await self._get_containing_fences(entity)
        current_ids = {str(f["id"]) for f in current_fences}

        prev_ids = self._inside.get(entity_key, set())

        # ENTER events — new fences
        for fence_id in current_ids - prev_ids:
            fence = next((f for f in current_fences if str(f["id"]) == fence_id), None)
            if fence:
                events.append(SentinelEvent(
                    event_type=EventType.GEOFENCE_ENTER,
                    entity_id=entity.entity_id,
                    entity_type=entity.entity_type,
                    source_id=entity.source_id,
                    track_id=entity.track_id,
                    severity=Severity.MEDIUM,
                    position=entity.position,
                    reason=f"Entered geofence: {fence.get('name', fence_id)}",
                    trace_id=entity.trace_id,
                    metadata={
                        "geofence_id": fence_id,
                        "geofence_name": fence.get("name", ""),
                    },
                ))

        # EXIT events — left fences
        for fence_id in prev_ids - current_ids:
            events.append(SentinelEvent(
                event_type=EventType.GEOFENCE_EXIT,
                entity_id=entity.entity_id,
                entity_type=entity.entity_type,
                source_id=entity.source_id,
                track_id=entity.track_id,
                severity=Severity.MEDIUM,
                position=entity.position,
                reason=f"Exited geofence: {fence_id}",
                trace_id=entity.trace_id,
                metadata={"geofence_id": fence_id},
            ))

        self._inside[entity_key] = current_ids

        # Trim cache
        if len(self._inside) > 200_000:
            keys = list(self._inside.keys())
            for k in keys[:50_000]:
                del self._inside[k]

        return events

    async def _get_containing_fences(self, entity: EntityState) -> list[dict[str, Any]]:
        """Query PostGIS for geofences containing this point."""
        try:
            async with self._db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, name, description, alert_on, entity_types
                    FROM geofences
                    WHERE active = TRUE
                      AND ST_Contains(
                          geometry,
                          ST_SetSRID(ST_MakePoint($1, $2), 4326)
                      )
                      AND (entity_types IS NULL OR $3 = ANY(entity_types))
                    """,
                    entity.position.longitude,
                    entity.position.latitude,
                    entity.entity_type.value,
                )
                return [dict(row) for row in rows]
        except Exception:
            log.exception("geofence.query_error")
            return []

    async def create_geofence(
        self,
        name: str,
        geometry_wkt: str,
        description: str = "",
        entity_types: Optional[list[str]] = None,
        alert_on: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new geofence zone."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO geofences (name, description, geometry, entity_types, alert_on)
                VALUES ($1, $2, ST_GeomFromText($3, 4326), $4, $5)
                RETURNING id, name, description, active, created_at
                """,
                name,
                description,
                geometry_wkt,
                entity_types,
                alert_on or ["ENTER", "EXIT", "DWELL"],
            )
            return dict(row)

    async def list_geofences(self) -> list[dict[str, Any]]:
        """List all active geofences."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, description, ST_AsGeoJSON(geometry) as geometry_json,
                       alert_on, entity_types, active, created_at
                FROM geofences
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in rows]
