"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.requests import Request
from starlette.responses import Response

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.storage.redis_cache import RedisCache
from sentinel.storage.timescale import TimescaleStore


def create_app(
    db: TimescaleStore,
    cache: RedisCache,
    bus: MessageBus,
    settings: Settings,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Sentinel — World Awareness Engine",
        description="Real-time geospatial intelligence API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store dependencies on app state
    app.state.db = db
    app.state.cache = cache
    app.state.bus = bus
    app.state.settings = settings

    # ── Register routes ───────────────────────────────────────
    from sentinel.api.routes.health import router as health_router
    from sentinel.api.routes.entities import router as entities_router
    from sentinel.api.routes.events import router as events_router
    from sentinel.api.routes.geofences import router as geofences_router
    from sentinel.api.routes.ws import router as ws_router

    app.include_router(health_router, tags=["Health"])
    app.include_router(entities_router, prefix="/api/v1", tags=["Entities"])
    app.include_router(events_router, prefix="/api/v1", tags=["Events"])
    app.include_router(geofences_router, prefix="/api/v1", tags=["Geofences"])
    app.include_router(ws_router, prefix="/api/v1", tags=["WebSocket"])

    # ── Prometheus metrics endpoint ───────────────────────────
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ── Serve frontend static files (production build) ────────
    # Must be mounted LAST so API routes take precedence.
    static_dir = os.path.join(os.path.dirname(__file__), "../../static")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
