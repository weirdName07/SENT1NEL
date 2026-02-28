"""Velocity estimation and smoothing."""

from __future__ import annotations

import math

from sentinel.core.schemas import EntityState, Velocity
from sentinel.processing.kalman import haversine_m


def estimate_velocity(current: EntityState, previous: EntityState) -> Velocity | None:
    """
    Estimate velocity from two sequential observations using Haversine.

    Returns estimated Velocity or None if insufficient data.
    """
    if not current.timestamp or not previous.timestamp:
        return None

    dt = (current.timestamp - previous.timestamp).total_seconds()
    if dt <= 0:
        return None

    dist_m = haversine_m(
        previous.position.latitude,
        previous.position.longitude,
        current.position.latitude,
        current.position.longitude,
    )

    speed_mps = dist_m / dt

    # Heading
    dlat = current.position.latitude - previous.position.latitude
    dlon = current.position.longitude - previous.position.longitude
    heading_deg = math.degrees(math.atan2(dlon, dlat)) % 360

    # Vertical rate
    vrate = None
    if current.position.altitude_m is not None and previous.position.altitude_m is not None:
        vrate = (current.position.altitude_m - previous.position.altitude_m) / dt

    return Velocity(
        speed_mps=round(speed_mps, 2),
        heading_deg=round(heading_deg, 2),
        vertical_rate_mps=round(vrate, 2) if vrate is not None else None,
    )
