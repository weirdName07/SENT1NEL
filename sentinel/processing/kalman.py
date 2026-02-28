"""Constant-velocity Kalman filter for 6-DOF entity tracking."""

from __future__ import annotations

import math

import numpy as np

# Earth radius in meters (WGS84 mean)
EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two WGS84 points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class KalmanFilter6DOF:
    """
    Constant-velocity Kalman filter for geospatial entity tracking.

    State vector: [lat, lon, alt, vlat, vlon, valt]
      - lat, lon in degrees
      - alt in meters
      - vlat, vlon in degrees/second
      - valt in meters/second

    This is a simplified linear KF operating in geographic coordinates.
    For very high accuracy at polar regions or long prediction windows,
    a UKF/EKF in ECEF would be superior, but this is sufficient for
    track stitching and anomaly detection at operational scale.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        alt: float = 0.0,
        speed_mps: float = 0.0,
        heading_deg: float = 0.0,
        vrate_mps: float = 0.0,
        position_noise: float = 0.001,   # degrees (~100m)
        velocity_noise: float = 0.0001,  # degrees/s
        measurement_noise: float = 0.001,
    ) -> None:
        # Convert speed + heading to velocity components
        vlat = 0.0
        vlon = 0.0
        if speed_mps > 0 and heading_deg is not None:
            heading_rad = math.radians(heading_deg)
            # Approximate deg/s from m/s
            vlat = (speed_mps * math.cos(heading_rad)) / (EARTH_RADIUS_M * math.pi / 180)
            vlon = (speed_mps * math.sin(heading_rad)) / (
                EARTH_RADIUS_M * math.cos(math.radians(lat)) * math.pi / 180
            )

        # State: [lat, lon, alt, vlat, vlon, valt]
        self.x = np.array([lat, lon, alt, vlat, vlon, vrate_mps], dtype=np.float64)

        # State covariance
        self.P = np.diag([
            position_noise**2,
            position_noise**2,
            1000.0**2,  # altitude uncertainty
            velocity_noise**2,
            velocity_noise**2,
            1.0**2,     # vertical rate uncertainty
        ])

        # Measurement noise
        self._R = np.diag([
            measurement_noise**2,
            measurement_noise**2,
            500.0**2,
            velocity_noise**2,
            velocity_noise**2,
            0.5**2,
        ])

        # Process noise scale
        self._q_pos = position_noise
        self._q_vel = velocity_noise

    def predict(self, dt: float) -> np.ndarray:
        """
        Predict state forward by dt seconds.

        Returns predicted state vector [lat, lon, alt, vlat, vlon, valt].
        """
        if dt <= 0:
            return self.x.copy()

        # State transition: constant velocity
        F = np.eye(6)
        F[0, 3] = dt  # lat += vlat * dt
        F[1, 4] = dt  # lon += vlon * dt
        F[2, 5] = dt  # alt += valt * dt

        x_pred = F @ self.x

        # Process noise
        q = dt
        Q = np.diag([
            (self._q_pos * q)**2,
            (self._q_pos * q)**2,
            (100 * q)**2,
            (self._q_vel * q)**2,
            (self._q_vel * q)**2,
            (0.1 * q)**2,
        ])

        self.P = F @ self.P @ F.T + Q
        self.x = x_pred

        return self.x.copy()

    def update(
        self,
        lat: float,
        lon: float,
        alt: float = 0.0,
        speed_mps: float | None = None,
        heading_deg: float | None = None,
        vrate_mps: float | None = None,
    ) -> np.ndarray:
        """
        Kalman measurement update with new observation.

        Returns updated state vector.
        """
        # Build measurement vector
        vlat_meas = self.x[3]  # default: keep predicted
        vlon_meas = self.x[4]
        valt_meas = vrate_mps if vrate_mps is not None else self.x[5]

        if speed_mps is not None and heading_deg is not None and speed_mps > 0:
            heading_rad = math.radians(heading_deg)
            vlat_meas = (speed_mps * math.cos(heading_rad)) / (EARTH_RADIUS_M * math.pi / 180)
            cos_lat = math.cos(math.radians(lat))
            if abs(cos_lat) > 1e-6:
                vlon_meas = (speed_mps * math.sin(heading_rad)) / (
                    EARTH_RADIUS_M * cos_lat * math.pi / 180
                )

        z = np.array([lat, lon, alt, vlat_meas, vlon_meas, valt_meas])

        # Observation matrix (direct observation)
        H = np.eye(6)

        # Innovation
        y = z - H @ self.x

        # Handle longitude wrapping
        if y[1] > 180:
            y[1] -= 360
        elif y[1] < -180:
            y[1] += 360

        S = H @ self.P @ H.T + self._R
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P

        return self.x.copy()

    @property
    def position(self) -> tuple[float, float, float]:
        """Return (lat, lon, alt)."""
        return float(self.x[0]), float(self.x[1]), float(self.x[2])

    @property
    def velocity_mps(self) -> float:
        """Return estimated speed in m/s."""
        vlat_mps = self.x[3] * EARTH_RADIUS_M * math.pi / 180
        vlon_mps = self.x[4] * EARTH_RADIUS_M * math.cos(math.radians(self.x[0])) * math.pi / 180
        return float(math.sqrt(vlat_mps**2 + vlon_mps**2 + self.x[5]**2))

    @property
    def heading_deg(self) -> float:
        """Return estimated heading in degrees."""
        vlat_mps = self.x[3]
        vlon_mps = self.x[4]
        return float(math.degrees(math.atan2(vlon_mps, vlat_mps))) % 360

    def mahalanobis_distance(self, lat: float, lon: float, alt: float = 0.0) -> float:
        """
        Mahalanobis distance between a candidate position and predicted state.
        Used for gating in track association.
        """
        z = np.array([lat, lon, alt])
        x_pos = self.x[:3]
        P_pos = self.P[:3, :3]

        diff = z - x_pos
        # Handle longitude wrapping
        if diff[1] > 180:
            diff[1] -= 360
        elif diff[1] < -180:
            diff[1] += 360

        try:
            P_inv = np.linalg.inv(P_pos)
            d2 = float(diff.T @ P_inv @ diff)
            return math.sqrt(max(0, d2))
        except np.linalg.LinAlgError:
            return float("inf")
