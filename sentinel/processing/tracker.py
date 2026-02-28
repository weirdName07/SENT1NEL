"""Motion-model track stitcher — Kalman-based track association and management."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4

import structlog

from sentinel.core.events import EventType, SentinelEvent, Severity
from sentinel.core.schemas import EntityLifecycle, EntityState, EntityType
from sentinel.observability.metrics import active_tracks, track_associations
from sentinel.processing.kalman import KalmanFilter6DOF, haversine_m

log = structlog.get_logger()


# ── Gating Parameters per Entity Type ────────────────────────

@dataclass
class GatingParams:
    gate_radius_km: float
    max_speed_change_mps: float
    heading_window_deg: float
    mahalanobis_threshold: float = 10.0


GATING = {
    EntityType.AIRCRAFT: GatingParams(50.0, 100.0, 45.0),
    EntityType.VESSEL: GatingParams(10.0, 5.0, 30.0),
    EntityType.SATELLITE: GatingParams(200.0, 100.0, 10.0),
    EntityType.EARTHQUAKE: GatingParams(0, 0, 0),   # Not tracked
    EntityType.WEATHER: GatingParams(0, 0, 0),       # Not tracked
}

NON_TRACKED_TYPES = {EntityType.EARTHQUAKE, EntityType.WEATHER}


# ── Track State ──────────────────────────────────────────────

@dataclass
class TrackState:
    track_id: UUID
    source_id: str
    entity_type: EntityType
    kf: KalmanFilter6DOF
    last_observation: datetime
    observation_count: int = 1
    lifecycle: EntityLifecycle = EntityLifecycle.NEW
    last_position: tuple[float, float, float] = (0, 0, 0)
    last_speed_mps: float = 0.0
    last_heading_deg: float = 0.0


class TrackStitcher:
    """
    Motion-model-based track association and management.

    Algorithm:
    1. Fast path: source_id exact match (~90% of cases)
    2. If miss: predict positions of active tracks, gate by Mahalanobis distance
    3. Velocity consistency check
    4. Nearest-neighbor among gated candidates
    5. No match → create new track
    """

    def __init__(self) -> None:
        # source_key → TrackState
        self._tracks: dict[str, TrackState] = {}
        # track_id → source_key (for reverse lookup)
        self._track_index: dict[UUID, str] = {}

    @property
    def active_track_count(self) -> int:
        return len(self._tracks)

    def associate(self, entity: EntityState) -> tuple[EntityState, list[SentinelEvent]]:
        """
        Associate an observation with a track.

        Returns the updated entity (with track_id, observation_count) and any events.
        """
        events: list[SentinelEvent] = []

        # Non-tracked entity types get a pass-through track
        if entity.entity_type in NON_TRACKED_TYPES:
            entity.track_id = entity.entity_id  # Self-referencing
            entity.observation_count = 1
            return entity, events

        source_key = entity.entity_key
        now = entity.timestamp or datetime.now(timezone.utc)

        # ── Fast path: exact source_id match ──────────────────
        track = self._tracks.get(source_key)
        if track is not None:
            dt = (now - track.last_observation).total_seconds()
            if dt > 0:
                track.kf.predict(dt)
            track.kf.update(
                lat=entity.position.latitude,
                lon=entity.position.longitude,
                alt=entity.position.altitude_m or 0,
                speed_mps=entity.velocity.speed_mps if entity.velocity else None,
                heading_deg=entity.velocity.heading_deg if entity.velocity else None,
                vrate_mps=entity.velocity.vertical_rate_mps if entity.velocity else None,
            )
            track.last_observation = now
            track.observation_count += 1
            track.last_position = track.kf.position
            track.last_speed_mps = track.kf.velocity_mps
            track.last_heading_deg = track.kf.heading_deg

            entity.track_id = track.track_id
            entity.observation_count = track.observation_count

            track_associations.labels(method="exact_match").inc()
            return entity, events

        # ── Slow path: motion-based association ───────────────
        gating = GATING.get(entity.entity_type)
        if gating and gating.gate_radius_km > 0:
            best_track, best_distance = self._find_nearest_track(entity, now, gating)
            if best_track is not None:
                # Velocity consistency check
                if self._velocity_consistent(entity, best_track, gating):
                    dt = (now - best_track.last_observation).total_seconds()
                    best_track.kf.update(
                        lat=entity.position.latitude,
                        lon=entity.position.longitude,
                        alt=entity.position.altitude_m or 0,
                        speed_mps=entity.velocity.speed_mps if entity.velocity else None,
                        heading_deg=entity.velocity.heading_deg if entity.velocity else None,
                    )
                    best_track.last_observation = now
                    best_track.observation_count += 1
                    best_track.source_id = entity.source_id
                    best_track.last_position = best_track.kf.position

                    # Re-index with new source_id
                    old_key = self._track_index.get(best_track.track_id)
                    if old_key and old_key in self._tracks:
                        del self._tracks[old_key]
                    self._tracks[source_key] = best_track
                    self._track_index[best_track.track_id] = source_key

                    entity.track_id = best_track.track_id
                    entity.observation_count = best_track.observation_count

                    track_associations.labels(method="kalman").inc()
                    return entity, events

        # ── No match: create new track ────────────────────────
        new_track = self._create_track(entity, now)
        entity.track_id = new_track.track_id
        entity.observation_count = 1

        events.append(SentinelEvent(
            event_type=EventType.TRACK_CREATED,
            entity_type=entity.entity_type,
            source_id=entity.source_id,
            track_id=new_track.track_id,
            position=entity.position,
            severity=Severity.LOW,
            reason=f"New track for {entity.entity_type.value}:{entity.source_id}",
            trace_id=entity.trace_id,
        ))

        track_associations.labels(method="new_track").inc()
        self._update_metrics()
        return entity, events

    def _find_nearest_track(
        self,
        entity: EntityState,
        now: datetime,
        gating: GatingParams,
    ) -> tuple[TrackState | None, float]:
        """Find nearest track within gating distance using Mahalanobis distance."""
        best: TrackState | None = None
        best_dist = float("inf")

        for track in self._tracks.values():
            if track.entity_type != entity.entity_type:
                continue

            dt = (now - track.last_observation).total_seconds()
            if dt <= 0:
                continue

            # Predict track position to current time
            track.kf.predict(dt)
            pred_lat, pred_lon, pred_alt = track.kf.position

            # Euclidean gate first (fast rejection)
            dist_km = haversine_m(
                entity.position.latitude, entity.position.longitude,
                pred_lat, pred_lon,
            ) / 1000.0

            if dist_km > gating.gate_radius_km:
                continue

            # Mahalanobis distance (more precise)
            mahala = track.kf.mahalanobis_distance(
                entity.position.latitude,
                entity.position.longitude,
                entity.position.altitude_m or 0,
            )

            if mahala < gating.mahalanobis_threshold and mahala < best_dist:
                best = track
                best_dist = mahala

        return best, best_dist

    def _velocity_consistent(
        self,
        entity: EntityState,
        track: TrackState,
        gating: GatingParams,
    ) -> bool:
        """Check if observation velocity is consistent with track history."""
        if entity.velocity is None or entity.velocity.speed_mps is None:
            return True  # No velocity to check — allow association

        speed_diff = abs((entity.velocity.speed_mps or 0) - track.last_speed_mps)
        if speed_diff > gating.max_speed_change_mps:
            return False

        if entity.velocity.heading_deg is not None and track.last_heading_deg is not None:
            heading_diff = abs(entity.velocity.heading_deg - track.last_heading_deg)
            heading_diff = min(heading_diff, 360 - heading_diff)
            if heading_diff > gating.heading_window_deg:
                return False

        return True

    def _create_track(self, entity: EntityState, now: datetime) -> TrackState:
        """Create a new track from an observation."""
        track_id = uuid4()
        kf = KalmanFilter6DOF(
            lat=entity.position.latitude,
            lon=entity.position.longitude,
            alt=entity.position.altitude_m or 0,
            speed_mps=entity.velocity.speed_mps if entity.velocity and entity.velocity.speed_mps else 0,
            heading_deg=entity.velocity.heading_deg if entity.velocity and entity.velocity.heading_deg else 0,
            vrate_mps=entity.velocity.vertical_rate_mps if entity.velocity and entity.velocity.vertical_rate_mps else 0,
        )
        track = TrackState(
            track_id=track_id,
            source_id=entity.source_id,
            entity_type=entity.entity_type,
            kf=kf,
            last_observation=now,
            last_position=kf.position,
            last_speed_mps=kf.velocity_mps,
            last_heading_deg=kf.heading_deg,
        )
        source_key = entity.entity_key
        self._tracks[source_key] = track
        self._track_index[track_id] = source_key
        return track

    def remove_track(self, track_id: UUID) -> None:
        """Remove a track (called by lifecycle manager on eviction)."""
        source_key = self._track_index.pop(track_id, None)
        if source_key:
            self._tracks.pop(source_key, None)
        self._update_metrics()

    def _update_metrics(self) -> None:
        """Update Prometheus active track gauges."""
        counts: dict[str, int] = {}
        for track in self._tracks.values():
            t = track.entity_type.value
            counts[t] = counts.get(t, 0) + 1
        for etype, count in counts.items():
            active_tracks.labels(entity_type=etype).set(count)
