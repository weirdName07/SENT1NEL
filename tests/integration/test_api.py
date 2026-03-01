"""Integration test — API routes with mocked dependencies."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sentinel.api.app import create_app
from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.storage.redis_cache import RedisCache
from sentinel.storage.timescale import TimescaleStore


@pytest.fixture
def mock_db():
    db = MagicMock(spec=TimescaleStore)
    db.is_healthy = AsyncMock(return_value=True)
    db.query_entities = AsyncMock(return_value=[])
    db.pool = MagicMock()
    db.pool.acquire = MagicMock()
    return db


@pytest.fixture
def mock_cache():
    cache = MagicMock(spec=RedisCache)
    cache.is_healthy = AsyncMock(return_value=True)
    cache.get_entities_in_bbox = AsyncMock(return_value=[])
    return cache


@pytest.fixture
def mock_bus():
    bus = MagicMock(spec=MessageBus)
    bus._nc = MagicMock()
    bus._nc.is_connected = True
    bus.nc = bus._nc
    return bus


@pytest.fixture
def client(mock_db, mock_cache, mock_bus):
    settings = Settings(
        nats_url="nats://localhost:4222",
        db_host="localhost",
        db_password="test",
    )
    app = create_app(mock_db, mock_cache, mock_bus, settings)
    return TestClient(app)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "uptime_s" in data

    def test_ready_all_healthy(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["timescaledb"] is True
        assert data["redis"] is True
        assert data["nats"] is True

    def test_ready_db_down(self, client, mock_db):
        mock_db.is_healthy = AsyncMock(return_value=False)
        resp = client.get("/ready")
        data = resp.json()
        assert data["ready"] is False
        assert data["timescaledb"] is False

    def test_metrics_endpoint(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "sentinel_" in resp.text


class TestEntityEndpoints:
    def test_list_entities_empty(self, client):
        resp = client.get("/api/v1/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["entities"] == []

    def test_list_entities_with_type_filter(self, client, mock_db):
        mock_db.query_entities = AsyncMock(return_value=[
            {"id": "test-id", "entity_type": "aircraft", "source_id": "abc",
             "observed_at": datetime.now(timezone.utc)},
        ])
        resp = client.get("/api/v1/entities?entity_type=aircraft&limit=10")
        assert resp.status_code == 200

    def test_list_entities_with_bbox(self, client):
        resp = client.get(
            "/api/v1/entities?min_lon=-80&min_lat=35&max_lon=-70&max_lat=45"
        )
        assert resp.status_code == 200

    def test_live_entities(self, client):
        resp = client.get("/api/v1/entities/live?lon=0&lat=0&radius_km=500")
        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data


class TestEventEndpoints:
    def test_list_events_empty(self, client, mock_db):
        # Mock the pool.acquire context manager for direct SQL queries
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = client.get("/api/v1/events")
        assert resp.status_code == 200


class TestGeofenceEndpoints:
    def test_list_geofences(self, client, mock_db):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = client.get("/api/v1/geofences")
        assert resp.status_code == 200

    def test_create_geofence(self, client, mock_db):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "test-id", "name": "Test Zone",
            "description": "Test", "active": True,
            "created_at": datetime.now(timezone.utc),
        })
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = client.post("/api/v1/geofences", json={
            "name": "Test Zone",
            "geometry_wkt": "POLYGON((-74 40, -73 40, -73 41, -74 41, -74 40))",
        })
        assert resp.status_code == 200
