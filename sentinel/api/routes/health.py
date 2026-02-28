"""Health, readiness, and liveness endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health():
    """Basic liveness probe."""
    return {
        "status": "healthy",
        "uptime_s": round(time.time() - _start_time, 1),
    }


@router.get("/ready")
async def ready(request: Request):
    """Readiness probe — checks all downstream dependencies."""
    db_ok = await request.app.state.db.is_healthy()
    cache_ok = await request.app.state.cache.is_healthy()
    nats_ok = request.app.state.bus.nc.is_connected if request.app.state.bus._nc else False

    all_ok = db_ok and cache_ok and nats_ok

    return {
        "ready": all_ok,
        "timescaledb": db_ok,
        "redis": cache_ok,
        "nats": nats_ok,
    }
