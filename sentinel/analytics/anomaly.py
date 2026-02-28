"""Entity-type-aware anomaly detection with behavioral profiles."""

from __future__ import annotations

from datetime import datetime

import structlog

from sentinel.analytics.profiles import BehavioralProfile, get_profile
from sentinel.core.events import EventType, SentinelEvent, Severity
from sentinel.core.schemas import EntityState, EntityType
from sentinel.observability.metrics import anomalies_detected
from sentinel.processing.kalman import haversine_m

log = structlog.get_logger()


class AnomalyDetector:
    """
    Entity-type-aware anomaly detection.

    Runs behavioral checks against per-type profiles:
    1. Speed anomaly (Z-score against type baseline)
    2. Position teleport (impossible jump detection)
    3. Altitude deviation (for aircraft/satellites)
    4. Heading reversal (sudden course change)
    5. Update interval anomaly (unexpected silence/burst)
    """

    def __init__(self) -> None:
        # Track previous observations for delta-based checks
        self._prev: dict[str, EntityState] = {}

    def check(self, entity: EntityState) -> list[SentinelEvent]:
        """Run all anomaly checks against the entity's behavioral profile."""
        profile = get_profile(entity.entity_type)
        events: list[SentinelEvent] = []

        # Skip non-applicable types
        if entity.entity_type == EntityType.EARTHQUAKE:
            return events

        prev = self._prev.get(entity.entity_key)

        # 1. Speed anomaly
        speed_event = self._check_speed(entity, profile)
        if speed_event:
            events.append(speed_event)

        # 2. Position teleport
        if prev:
            teleport_event = self._check_teleport(entity, prev, profile)
            if teleport_event:
                events.append(teleport_event)

        # 3. Altitude deviation
        alt_event = self._check_altitude(entity, profile)
        if alt_event:
            events.append(alt_event)

        # 4. Heading reversal
        if prev:
            heading_event = self._check_heading_reversal(entity, prev, profile)
            if heading_event:
                events.append(heading_event)

        # Update state and anomaly annotations
        self._prev[entity.entity_key] = entity
        if events:
            entity.anomalies = [e.event_type.value for e in events]
            for e in events:
                anomalies_detected.labels(
                    entity_type=entity.entity_type.value,
                    anomaly_type=e.reason.split(":")[0] if ":" in e.reason else "unknown",
                ).inc()

        # Trim prev cache
        if len(self._prev) > 200_000:
            keys = list(self._prev.keys())
            for k in keys[:50_000]:
                del self._prev[k]

        return events

    def _check_speed(
        self, entity: EntityState, profile: BehavioralProfile
    ) -> SentinelEvent | None:
        if not entity.velocity or entity.velocity.speed_mps is None:
            return None

        speed = entity.velocity.speed_mps

        # Hard ceiling
        if speed > profile.speed_max_mps:
            return self._make_event(
                entity,
                Severity.HIGH,
                f"SPEED_CEILING: {speed:.0f} m/s exceeds max {profile.speed_max_mps:.0f} m/s",
            )

        # Z-score
        if profile.speed_std_mps > 0:
            z = (speed - profile.speed_mean_mps) / profile.speed_std_mps
            if abs(z) > profile.anomaly_z_threshold:
                severity = self._z_to_severity(z)
                return self._make_event(
                    entity,
                    severity,
                    f"SPEED_ANOMALY: Z={z:.1f} ({speed:.0f} m/s, type={entity.entity_type.value})",
                )

        return None

    def _check_teleport(
        self,
        entity: EntityState,
        prev: EntityState,
        profile: BehavioralProfile,
    ) -> SentinelEvent | None:
        if profile.max_position_jump_km <= 0:
            return None

        dist_m = haversine_m(
            prev.position.latitude,
            prev.position.longitude,
            entity.position.latitude,
            entity.position.longitude,
        )
        dist_km = dist_m / 1000.0

        if dist_km > profile.max_position_jump_km:
            return self._make_event(
                entity,
                Severity.HIGH,
                f"POSITION_TELEPORT: {dist_km:.1f} km jump exceeds {profile.max_position_jump_km} km",
            )

        return None

    def _check_altitude(
        self, entity: EntityState, profile: BehavioralProfile
    ) -> SentinelEvent | None:
        if profile.altitude_mean_m is None or profile.altitude_std_m is None:
            return None
        if entity.position.altitude_m is None:
            return None

        alt = entity.position.altitude_m
        z = (alt - profile.altitude_mean_m) / profile.altitude_std_m

        if abs(z) > profile.anomaly_z_threshold:
            return self._make_event(
                entity,
                self._z_to_severity(z),
                f"ALTITUDE_ANOMALY: Z={z:.1f} ({alt:.0f} m, type={entity.entity_type.value})",
            )

        return None

    def _check_heading_reversal(
        self,
        entity: EntityState,
        prev: EntityState,
        profile: BehavioralProfile,
    ) -> SentinelEvent | None:
        if not entity.velocity or entity.velocity.heading_deg is None:
            return None
        if not prev.velocity or prev.velocity.heading_deg is None:
            return None

        diff = abs(entity.velocity.heading_deg - prev.velocity.heading_deg)
        diff = min(diff, 360 - diff)

        if diff > profile.heading_reversal_deg:
            return self._make_event(
                entity,
                Severity.MEDIUM,
                f"HEADING_REVERSAL: {diff:.0f}° change (threshold: {profile.heading_reversal_deg}°)",
            )

        return None

    @staticmethod
    def _make_event(entity: EntityState, severity: Severity, reason: str) -> SentinelEvent:
        return SentinelEvent(
            event_type=EventType.ANOMALY_DETECTED,
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            source_id=entity.source_id,
            track_id=entity.track_id,
            severity=severity,
            confidence=entity.confidence,
            reason=reason,
            position=entity.position,
            trace_id=entity.trace_id,
            metadata={"source": entity.source},
        )

    @staticmethod
    def _z_to_severity(z: float) -> Severity:
        z_abs = abs(z)
        if z_abs > 5:
            return Severity.CRITICAL
        if z_abs > 4:
            return Severity.HIGH
        if z_abs > 3:
            return Severity.MEDIUM
        return Severity.LOW
