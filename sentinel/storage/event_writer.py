"""Event writer — NATS consumer that persists SentinelEvents to TimescaleDB."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import structlog

from sentinel.core.backpressure import BatchCoalescer
from sentinel.core.bus import MessageBus
from sentinel.core.constants import CONSUMER_EVENT_WRITER, STREAM_EVENTS, SUBJECT_EVENTS_ALL
from sentinel.core.events import SentinelEvent
from sentinel.observability.metrics import db_write_latency, events_emitted

log = structlog.get_logger()


class EventWriter:
    """
    Consumes events from NATS and batch-writes them to TimescaleDB.
    """

    def __init__(self, bus: MessageBus, pool, batch_size: int = 100) -> None:
        self._bus = bus
        self._pool = pool
        self._batcher = BatchCoalescer(batch_size=batch_size, flush_interval_s=2.0)

    async def run(self) -> None:
        sub = await self._bus.subscribe(
            subject=SUBJECT_EVENTS_ALL,
            stream=STREAM_EVENTS,
            consumer_name=CONSUMER_EVENT_WRITER,
            handler=None,  # Pull-based
            max_ack_pending=500,
        )

        log.info("event_writer.started")

        while True:
            try:
                msgs = await sub.fetch(batch=50, timeout=5)
                for msg in msgs:
                    event = SentinelEvent.deserialize(msg.data)
                    batch = self._batcher.add(event)
                    if batch:
                        await self._flush(batch)
                    await msg.ack()

                # Time-based flush
                if self._batcher.should_flush():
                    await self._flush(self._batcher.flush())

            except asyncio.CancelledError:
                # Final flush
                if self._batcher.pending > 0:
                    await self._flush(self._batcher.flush())
                raise
            except Exception as e:
                if "timeout" not in str(e).lower():
                    log.exception("event_writer.error")
                # Time-based flush on timeout
                if self._batcher.pending > 0:
                    await self._flush(self._batcher.flush())

    async def _flush(self, events: list[SentinelEvent]) -> None:
        if not events:
            return

        t0 = time.monotonic()

        rows = [
            (
                str(e.event_id),
                e.event_type.value,
                e.severity.value,
                e.timestamp,
                str(e.entity_id) if e.entity_id else None,
                e.entity_type.value if e.entity_type else None,
                e.source_id,
                str(e.track_id) if e.track_id else None,
                e.confidence,
                e.reason,
                f"SRID=4326;POINT({e.position.longitude} {e.position.latitude})" if e.position else None,
                e.metadata,
                e.trace_id,
            )
            for e in events
        ]

        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO events (
                    id, event_type, severity, timestamp,
                    entity_id, entity_type, source_id, track_id,
                    confidence, reason, position, metadata, trace_id
                ) VALUES (
                    $1::uuid, $2, $3, $4,
                    $5::uuid, $6, $7, $8::uuid,
                    $9, $10, ST_GeomFromEWKT($11), $12::jsonb, $13
                )
                """,
                rows,
            )

        elapsed = time.monotonic() - t0
        db_write_latency.observe(elapsed)
        for e in events:
            events_emitted.labels(event_type=e.event_type.value).inc()
        log.debug("event_writer.flushed", count=len(events), elapsed_ms=elapsed * 1000)
