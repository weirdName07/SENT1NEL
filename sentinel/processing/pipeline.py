"""Processing pipeline orchestrator — NATS consumer chain: normalize → enrich → track → store."""

from __future__ import annotations

import asyncio
import time

import orjson
import structlog

from sentinel.config import Settings
from sentinel.core.backpressure import BatchCoalescer
from sentinel.core.bus import MessageBus
from sentinel.core.constants import (
    CONSUMER_NORMALIZER,
    STREAM_RAW,
    SUBJECT_RAW_ALL,
)
from sentinel.core.lifecycle import LifecycleManager
from sentinel.core.schemas import EntityState
from sentinel.observability.metrics import e2e_latency, processing_latency
from sentinel.processing.enricher import Enricher
from sentinel.processing.normalizer import Normalizer
from sentinel.processing.tracker import TrackStitcher
from sentinel.storage.redis_cache import RedisCache
from sentinel.storage.timescale import TimescaleStore

log = structlog.get_logger()


class ProcessingPipeline:
    """
    Main processing pipeline.

    Consumes raw messages from NATS, runs them through:
      1. Normalizer (raw dict → EntityState)
      2. Enricher (confidence, metadata)
      3. Track Stitcher (Kalman association)
      4. Lifecycle update
      5. Batch write to TimescaleDB + Redis

    Events from the tracker are published back to NATS.
    """

    def __init__(
        self,
        bus: MessageBus,
        db: TimescaleStore,
        cache: RedisCache,
        settings: Settings,
    ) -> None:
        self._bus = bus
        self._db = db
        self._cache = cache
        self._settings = settings
        self._normalizer = Normalizer()
        self._enricher = Enricher()
        self._tracker = TrackStitcher()
        self._batcher = BatchCoalescer(
            batch_size=settings.db_write_batch_size,
            flush_interval_s=1.0,
        )
        self._lifecycle: LifecycleManager | None = None

    def set_lifecycle_manager(self, lifecycle: LifecycleManager) -> None:
        self._lifecycle = lifecycle

    async def run(self) -> None:
        """Main pipeline loop."""
        sub = await self._bus.subscribe(
            subject=SUBJECT_RAW_ALL,
            stream=STREAM_RAW,
            consumer_name=CONSUMER_NORMALIZER,
            handler=None,
            max_ack_pending=self._settings.nats_max_ack_pending,
        )

        log.info("pipeline.started")

        while True:
            try:
                msgs = await sub.fetch(batch=100, timeout=5)

                for msg in msgs:
                    entity = await self._process_message(msg.data)
                    if entity:
                        batch = self._batcher.add(entity)
                        if batch:
                            await self._flush_batch(batch)
                    await msg.ack()

                # Time-based flush
                if self._batcher.should_flush():
                    batch = self._batcher.flush()
                    if batch:
                        await self._flush_batch(batch)

            except asyncio.CancelledError:
                if self._batcher.pending > 0:
                    await self._flush_batch(self._batcher.flush())
                raise
            except Exception as e:
                if "timeout" not in str(e).lower():
                    log.exception("pipeline.error")
                # Flush on timeout too
                if self._batcher.pending > 0:
                    await self._flush_batch(self._batcher.flush())

    async def _process_message(self, data: bytes) -> EntityState | None:
        """Process a single raw message through the pipeline stages."""
        t0 = time.monotonic()

        # Stage 1: Normalize
        raw = orjson.loads(data)
        entity = self._normalizer.normalize(raw)
        if entity is None:
            return None

        t1 = time.monotonic()
        processing_latency.labels(stage="normalize").observe(t1 - t0)

        # Stage 2: Enrich
        entity = self._enricher.enrich(entity)
        t2 = time.monotonic()
        processing_latency.labels(stage="enrich").observe(t2 - t1)

        # Stage 3: Track stitching
        entity, events = self._tracker.associate(entity)
        t3 = time.monotonic()
        processing_latency.labels(stage="track").observe(t3 - t2)

        # Stage 4: Lifecycle update
        if self._lifecycle:
            lifecycle_state = await self._lifecycle.update_seen(
                entity.source_id, entity.entity_type
            )
            entity.lifecycle = lifecycle_state

        # Publish any events from tracker
        for event in events:
            await self._bus.publish(event.nats_subject, event.serialize())

        # Update Redis hot state
        await self._cache.set_entity(entity)

        # Track E2E latency
        if entity.timestamp:
            source_age = time.time() - entity.timestamp.timestamp()
            e2e_latency.labels(source=entity.source).observe(source_age)

        return entity

    async def _flush_batch(self, batch: list[EntityState]) -> None:
        """Write a batch of entities to TimescaleDB."""
        if not batch:
            return
        try:
            await self._db.insert_entities(batch)
            log.debug("pipeline.batch_flushed", count=len(batch))
        except Exception:
            log.exception("pipeline.batch_write_error", count=len(batch))
