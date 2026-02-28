"""Test configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_opensky_raw():
    """Sample raw OpenSky state vector data."""
    return {
        "source": "opensky",
        "entity_type": "aircraft",
        "source_id": "a1b2c3",
        "timestamp": 1709100000,
        "latitude": 40.7128,
        "longitude": -74.0060,
        "altitude_m": 10000,
        "speed_mps": 250.0,
        "heading_deg": 90.0,
        "vertical_rate_mps": 0.0,
        "on_ground": False,
        "callsign": "UAL123",
        "origin_country": "United States",
        "squawk": "1200",
    }


@pytest.fixture
def sample_usgs_raw():
    """Sample raw USGS earthquake data."""
    return {
        "source": "usgs",
        "entity_type": "earthquake",
        "source_id": "us7000n123",
        "timestamp": 1709100000,
        "latitude": 35.6762,
        "longitude": 139.6503,
        "altitude_m": -10000,
        "magnitude": 5.2,
        "place": "Near Tokyo, Japan",
        "felt": 142,
        "significance": 500,
        "tsunami": 0,
    }


@pytest.fixture
def sample_vessel_raw():
    """Sample raw AIS vessel data."""
    return {
        "source": "aisstream",
        "entity_type": "vessel",
        "source_id": "211234567",
        "timestamp": 1709100000,
        "latitude": 51.5074,
        "longitude": -0.1278,
        "altitude_m": 0,
        "speed_mps": 5.1,
        "heading_deg": 180.0,
        "name": "EVER GIVEN",
        "mmsi": "211234567",
        "ship_type": 70,
    }
