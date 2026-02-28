"""Entity-type behavioral profiles for anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sentinel.core.schemas import EntityType


@dataclass
class BehavioralProfile:
    """Per entity-type baseline thresholds for anomaly detection."""

    entity_type: EntityType

    # Speed baselines (m/s)
    speed_mean_mps: float
    speed_std_mps: float
    speed_max_mps: float            # Absolute ceiling

    # Altitude baselines (m, where applicable)
    altitude_mean_m: Optional[float] = None
    altitude_std_m: Optional[float] = None
    altitude_max_m: Optional[float] = None

    # Position delta baselines
    max_position_jump_km: float = 50.0  # Impossible teleport threshold

    # Temporal
    expected_update_interval_s: float = 10.0

    # Z-score threshold for flagging
    anomaly_z_threshold: float = 3.0

    # Heading reversal threshold (degrees)
    heading_reversal_deg: float = 150.0


# ── Default Profiles ──────────────────────────────────────────

PROFILES: dict[EntityType, BehavioralProfile] = {
    EntityType.AIRCRAFT: BehavioralProfile(
        entity_type=EntityType.AIRCRAFT,
        speed_mean_mps=220.0,         # ~430 kts cruise
        speed_std_mps=80.0,
        speed_max_mps=340.0,          # Mach 1 at sea level
        altitude_mean_m=10_000.0,
        altitude_std_m=3_000.0,
        altitude_max_m=15_000.0,
        max_position_jump_km=50.0,
        expected_update_interval_s=10.0,
        anomaly_z_threshold=3.0,
        heading_reversal_deg=150.0,
    ),
    EntityType.VESSEL: BehavioralProfile(
        entity_type=EntityType.VESSEL,
        speed_mean_mps=5.0,           # ~10 kts
        speed_std_mps=3.0,
        speed_max_mps=25.0,           # ~50 kts fast ferry
        altitude_mean_m=None,
        altitude_std_m=None,
        max_position_jump_km=5.0,
        expected_update_interval_s=30.0,
        anomaly_z_threshold=3.0,
        heading_reversal_deg=120.0,
    ),
    EntityType.SATELLITE: BehavioralProfile(
        entity_type=EntityType.SATELLITE,
        speed_mean_mps=7_500.0,       # LEO orbital velocity
        speed_std_mps=500.0,
        speed_max_mps=11_000.0,
        altitude_mean_m=500_000.0,
        altitude_std_m=200_000.0,
        altitude_max_m=36_000_000.0,  # GEO
        max_position_jump_km=500.0,
        expected_update_interval_s=3600.0,
        anomaly_z_threshold=4.0,      # More lenient for propagated data
    ),
    EntityType.EARTHQUAKE: BehavioralProfile(
        entity_type=EntityType.EARTHQUAKE,
        speed_mean_mps=0.0,
        speed_std_mps=0.0,
        speed_max_mps=0.0,
        max_position_jump_km=0.0,
        expected_update_interval_s=float("inf"),
        anomaly_z_threshold=float("inf"),  # Earthquakes don't have velocity anomalies
    ),
    EntityType.WEATHER: BehavioralProfile(
        entity_type=EntityType.WEATHER,
        speed_mean_mps=10.0,          # Wind speed
        speed_std_mps=15.0,
        speed_max_mps=100.0,          # Hurricane force
        max_position_jump_km=0.0,     # Weather stations don't move
        expected_update_interval_s=300.0,
        anomaly_z_threshold=3.0,
    ),
}


def get_profile(entity_type: EntityType) -> BehavioralProfile:
    """Get behavioral profile for an entity type."""
    return PROFILES[entity_type]
