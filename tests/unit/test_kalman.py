"""Unit tests for the Kalman filter."""

import math

from sentinel.processing.kalman import KalmanFilter6DOF, haversine_m


class TestHaversine:
    def test_zero_distance(self):
        dist = haversine_m(40.0, -74.0, 40.0, -74.0)
        assert dist == 0.0

    def test_known_distance(self):
        # NYC to London ≈ 5,570 km
        dist = haversine_m(40.7128, -74.0060, 51.5074, -0.1278)
        assert abs(dist / 1000 - 5570) < 100  # within 100 km

    def test_antipodal(self):
        dist = haversine_m(0, 0, 0, 180)
        assert abs(dist / 1000 - 20015) < 100  # half circumference


class TestKalmanFilter:
    def test_init_stationary(self):
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000)
        lat, lon, alt = kf.position
        assert abs(lat - 40.0) < 0.001
        assert abs(lon - (-74.0)) < 0.001

    def test_predict_stationary(self):
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000)
        kf.predict(10.0)  # 10 seconds
        lat, lon, alt = kf.position
        # Should barely move if stationary
        assert abs(lat - 40.0) < 0.1
        assert abs(lon - (-74.0)) < 0.1

    def test_predict_moving(self):
        # Aircraft heading north at ~250 m/s
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000, speed_mps=250, heading_deg=0)
        kf.predict(60.0)  # 60 seconds
        lat, lon, alt = kf.position
        # Should move north
        assert lat > 40.0

    def test_update_corrects_position(self):
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000)
        kf.predict(10.0)
        kf.update(lat=40.01, lon=-74.01, alt=10000)
        lat, lon, alt = kf.position
        # Should converge toward measurement
        assert abs(lat - 40.01) < 0.005
        assert abs(lon - (-74.01)) < 0.005

    def test_mahalanobis_nearby(self):
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000)
        dist = kf.mahalanobis_distance(40.001, -74.001, 10000)
        assert dist < 10  # Should be small for nearby point

    def test_mahalanobis_far(self):
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000)
        dist = kf.mahalanobis_distance(50.0, -74.0, 10000)
        assert dist > 100  # Should be large for distant point

    def test_velocity_estimation(self):
        kf = KalmanFilter6DOF(lat=40.0, lon=-74.0, alt=10000, speed_mps=250, heading_deg=90)
        assert kf.velocity_mps > 200  # Should reflect initial speed
