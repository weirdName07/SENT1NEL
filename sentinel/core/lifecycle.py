"""Entity lifecycle state machine — staleness detection, eviction, transition events."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.core.constants import REDIS_LIFECYCLE_PREFIX
from sentinel.core.events import EventType, SentinelEvent, Severity
from sentinel.core.schemas import EntityLifecycle, EntityType
from sentinel.storage.redis_cache import RedisCache

log = structlog.get_logger()


# ── Per-type staleness thresholds ─────────────────────────────

def _get_thresholds(settings: Settings) -> dict[EntityType, tuple[float, float]]:
    """Return (stale_s, lost_s) per entity type."""
    return {
        EntityType.AIRCRAFT: (settings.aircraft_stale_s, settings.aircraft_lost_s),
        EntityType.VESSEL: (settings.vessel_stale_s, settings.vessel_lost_s),
        EntityType.SATELLITE: (settings.satellite_stale_s, settings.satellite_lost_s),
        EntityType.EARTHQUAKE: (float("inf"), float("inf")),  # Events never stale
        EntityType.WEATHER: (settings.weather_stale_s, settings.weather_lost_s),
    }


class LifecycleManager:
    """
    Manages entity lifecycle transitions.

    Runs a background sweep that checks every entity's last-seen time
    against type-specific thresholds and transitions their state.
    Emits LIFECYCLE_TRANSITION events on every state change.
    """

    def __init__(
        self,
        bus: MessageBus,
        cache: RedisCache,
        settings: Settings,
    ) -> None:
        self._bus = bus
        self._cache = cache
        self._sweep_interval = settings.lifecycle_sweep_interval_s
        self._thresholds = _get_thresholds(settings)

    async def run(self) -> None:
        """Main lifecycle sweep loop."""
        log.info("lifecycle.started", sweep_interval_s=self._sweep_interval)
        while True:
            try:
                await self._sweep()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("lifecycle.sweep_error")
            await asyncio.sleep(self._sweep_interval)

    async def _sweep(self) -> None:
        """Scan all tracked entities and apply lifecycle transitions."""
        now = datetime.now(timezone.utc)
        keys = await self._cache.scan_prefix(REDIS_LIFECYCLE_PREFIX)

        transitions = 0
        evictions = 0

        for key in keys:
            data = await self._cache.hgetall(key)
            if not data:
                continue

            current_state = EntityLifecycle(data.get("state", "new"))
            last_seen_str = data.get("last_seen")
            entity_type_str = data.get("entity_type", "aircraft")
            source_id = data.get("source_id", "unknown")

            if not last_seen_str:
                continue

            last_seen = datetime.fromisoformat(last_seen_str)
            age_s = (now - last_seen).total_seconds()

            try:
                entity_type = EntityType(entity_type_str)
            except ValueError:
                continue

            stale_s, lost_s = self._thresholds.get(
                entity_type, (float("inf"), float("inf"))
            )

            # Determine target state
            new_state: Optional[EntityLifecycle] = None

            if current_state in (EntityLifecycle.NEW, EntityLifecycle.ACTIVE):
                if age_s > lost_s:
                    new_state = EntityLifecycle.LOST
                elif age_s > stale_s:
                    new_state = EntityLifecycle.STALE

            elif current_state == EntityLifecycle.STALE:
                if age_s > lost_s:
                    new_state = EntityLifecycle.LOST

            elif current_state == EntityLifecycle.LOST:
                # Lost → Archived after 2x lost threshold
                if age_s > lost_s * 2:
                    new_state = EntityLifecycle.ARCHIVED

            if new_state and new_state != current_state:
                await self._transition(
                    key, source_id, entity_type, current_state, new_state, now
                )
                transitions += 1

                if new_state == EntityLifecycle.ARCHIVED:
                    await self._evict(key, source_id, entity_type)
                    evictions += 1

        if transitions > 0:
            log.info(
                "lifecycle.sweep_complete",
                transitions=transitions,
                evictions=evictions,
                entities_scanned=len(keys),
            )

    async def _transition(
        self,
        key: str,
        source_id: str,
        entity_type: EntityType,
        from_state: EntityLifecycle,
        to_state: EntityLifecycle,
        now: datetime,
    ) -> None:
        """Apply a lifecycle transition and emit event."""
        await self._cache.hset(
            key,
            mapping={
                "state": to_state.value,
                "last_transition": now.isoformat(),
            },
        )

        event = SentinelEvent(
            event_type=EventType.LIFECYCLE_TRANSITION,
            source_id=source_id,
            entity_type=entity_type,
            severity=self._transition_severity(to_state),
            reason=f"Lifecycle: {from_state.value} → {to_state.value}",
            metadata={
                "from_state": from_state.value,
                "to_state": to_state.value,
            },
        )
        await self._bus.publish(event.nats_subject, event.serialize())

        log.debug(
            "lifecycle.transition",
            source_id=source_id,
            entity_type=entity_type.value,
            from_state=from_state.value,
            to_state=to_state.value,
        )

    async def _evict(
        self,
        key: str,
        source_id: str,
        entity_type: EntityType,
    ) -> None:
        """Remove archived entity from Redis hot cache."""
        await self._cache.delete(key)
        await self._cache.geo_remove(entity_type.value, source_id)
        log.debug("lifecycle.evicted", source_id=source_id)

    async def update_seen(
        self,
        source_id: str,
        entity_type: EntityType,
    ) -> EntityLifecycle:
        """
        Called by the processing pipeline on each new observation.
        Updates last_seen and transitions NEW→ACTIVE or STALE/LOST→ACTIVE.
        """
        key = f"{REDIS_LIFECYCLE_PREFIX}{source_id}:{entity_type.value}"
        now = datetime.now(timezone.utc)

        data = await self._cache.hgetall(key)
        current_state = EntityLifecycle(data.get("state", "new")) if data else EntityLifecycle.NEW

        if current_state == EntityLifecycle.NEW:
            new_state = EntityLifecycle.ACTIVE
        elif current_state in (EntityLifecycle.STALE, EntityLifecycle.LOST):
            new_state = EntityLifecycle.ACTIVE  # Re-acquisition
        else:
            new_state = EntityLifecycle.ACTIVE

        mapping = {
            "state": new_state.value,
            "last_seen": now.isoformat(),
            "entity_type": entity_type.value,
            "source_id": source_id,
        }

        # Emit transition event if state changed
        if current_state != new_state:
            mapping["last_transition"] = now.isoformat()

            if current_state in (EntityLifecycle.STALE, EntityLifecycle.LOST):
                event = SentinelEvent(
                    event_type=EventType.TRACK_REACQUIRED,
                    source_id=source_id,
                    entity_type=entity_type,
                    severity=Severity.MEDIUM,
                    reason=f"Re-acquired from {current_state.value}",
                    metadata={"from_state": current_state.value},
                )
                await self._bus.publish(event.nats_subject, event.serialize())

        await self._cache.hset(key, mapping=mapping)
        return new_state

    @staticmethod
    def _transition_severity(to_state: EntityLifecycle) -> Severity:
        if to_state == EntityLifecycle.ARCHIVED:
            return Severity.LOW
        if to_state == EntityLifecycle.LOST:
            return Severity.MEDIUM
        if to_state == EntityLifecycle.STALE:
            return Severity.LOW
        return Severity.LOW
