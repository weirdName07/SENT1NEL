"""Sentinel application entry point."""

import asyncio
import signal
import sys

import structlog

from sentinel.config import get_settings
from sentinel.observability.logging import setup_logging


log = structlog.get_logger()


async def main() -> None:
    """Boot the Sentinel engine."""
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)

    log.info("sentinel.boot", version="0.1.0")

    # ── Connect infrastructure ────────────────────────────────
    from sentinel.core.bus import MessageBus
    from sentinel.storage.timescale import TimescaleStore
    from sentinel.storage.redis_cache import RedisCache

    bus = MessageBus(settings.nats_url)
    db = TimescaleStore(settings)
    cache = RedisCache(settings.redis_url)

    await bus.connect()
    await db.connect()
    await cache.connect()

    log.info("sentinel.infra_ready")

    # ── Run database migrations ───────────────────────────────
    await db.run_migrations()

    # ── Start ingestion connectors ────────────────────────────
    from sentinel.ingestion.opensky import OpenSkyConnector
    from sentinel.ingestion.openmeteo import OpenMeteoConnector
    from sentinel.ingestion.geopolitics import GeopoliticsConnector
    from sentinel.ingestion.synthetic_flights import SyntheticFlightsConnector
    from sentinel.ingestion.celestrak import CelesTrakConnector
    from sentinel.ingestion.usgs import USGSConnector
    from sentinel.ingestion.aisstream import AISStreamConnector

    connectors = [
        OpenSkyConnector(bus, settings),
        OpenMeteoConnector(bus, settings),
        GeopoliticsConnector(bus, settings),
        SyntheticFlightsConnector(bus, settings, count=500),
        CelesTrakConnector(bus, settings),
        USGSConnector(bus, settings),
    ]

    # AIS requires an API key — only start if configured
    if settings.aisstream_api_key:
        connectors.append(AISStreamConnector(bus, settings))

    # ── Start event writer ────────────────────────────────────
    from sentinel.storage.event_writer import EventWriter

    event_writer = EventWriter(bus, db.pool)

    # ── Start processing pipeline ─────────────────────────────
    from sentinel.processing.pipeline import ProcessingPipeline

    pipeline = ProcessingPipeline(bus, db, cache, settings)

    # ── Start lifecycle manager ───────────────────────────────
    from sentinel.core.lifecycle import LifecycleManager

    lifecycle = LifecycleManager(bus, cache, settings)

    # ── NATS → Redis event bridge ─────────────────────────────
    # Subscribes to all events on NATS and republishes them to the
    # Redis pub/sub channel so the WebSocket fan-out can deliver
    # them to connected frontends.
    async def event_bridge() -> None:
        """Bridge NATS events → Redis pub/sub for WS fan-out."""
        import nats

        sub = await bus._nc.subscribe("sentinel.events.>")
        log.info("event_bridge.started", subject="sentinel.events.>")
        async for msg in sub.messages:
            try:
                await cache.publish("sentinel:events", msg.data)
            except Exception:
                log.exception("event_bridge.publish_error")

    # ── Start API server ──────────────────────────────────────
    from sentinel.api.app import create_app
    import uvicorn

    app = create_app(db, cache, bus, settings)
    api_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
    )
    api_server = uvicorn.Server(api_config)

    # ── Launch all tasks ──────────────────────────────────────
    tasks = []
    for connector in connectors:
        tasks.append(asyncio.create_task(connector.run(), name=f"connector:{connector.name}"))
    tasks.append(asyncio.create_task(pipeline.run(), name="pipeline"))
    tasks.append(asyncio.create_task(lifecycle.run(), name="lifecycle"))
    tasks.append(asyncio.create_task(event_writer.run(), name="event_writer"))
    tasks.append(asyncio.create_task(event_bridge(), name="event_bridge"))
    tasks.append(asyncio.create_task(api_server.serve(), name="api"))

    log.info("sentinel.running", tasks=len(tasks))

    # ── Graceful shutdown ─────────────────────────────────────
    stop = asyncio.Event()

    def _signal_handler() -> None:
        log.info("sentinel.shutdown_requested")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        log.info("sentinel.shutting_down")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bus.close()
        await db.close()
        await cache.close()
        log.info("sentinel.stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
