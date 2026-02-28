"""Backpressure controller — rate limiting, batch coalescing, consumer lag monitoring."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

import structlog
from prometheus_client import Gauge, Histogram

log = structlog.get_logger()

# ── Prometheus metrics ────────────────────────────────────────

consumer_lag = Gauge(
    "sentinel_nats_consumer_lag",
    "Pending messages for consumer",
    ["stream", "consumer"],
)
consumer_lag_seconds = Histogram(
    "sentinel_nats_consumer_lag_seconds",
    "Time between publish and consume",
    ["stream"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


class RateLimiter:
    """Token-bucket rate limiter for ingestion connectors."""

    def __init__(self, interval_s: float) -> None:
        self._interval = interval_s
        self._last_call = 0.0

    async def wait(self) -> None:
        """Wait until the next allowed call."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._interval:
            await asyncio.sleep(self._interval - elapsed)
        self._last_call = time.monotonic()


class BatchCoalescer:
    """
    Collects items and flushes either when batch_size is reached
    or when flush_interval expires — whichever comes first.
    """

    def __init__(self, batch_size: int = 500, flush_interval_s: float = 1.0) -> None:
        self._batch_size = batch_size
        self._flush_interval = flush_interval_s
        self._buffer: list = []
        self._last_flush = time.monotonic()

    def add(self, item: object) -> list | None:
        """
        Add an item. Returns the flushed batch if threshold is reached, else None.
        """
        self._buffer.append(item)
        if len(self._buffer) >= self._batch_size:
            return self.flush()
        if time.monotonic() - self._last_flush >= self._flush_interval:
            return self.flush()
        return None

    def flush(self) -> list:
        """Force flush and return current batch."""
        batch = self._buffer
        self._buffer = []
        self._last_flush = time.monotonic()
        return batch

    @property
    def pending(self) -> int:
        return len(self._buffer)

    def should_flush(self) -> bool:
        if not self._buffer:
            return False
        return (
            len(self._buffer) >= self._batch_size
            or time.monotonic() - self._last_flush >= self._flush_interval
        )


class LagMonitor:
    """Tracks consumer lag per stream and reports to Prometheus."""

    def __init__(self) -> None:
        self._lags: dict[str, int] = defaultdict(int)

    def record_lag(self, stream: str, consumer_name: str, pending: int) -> None:
        consumer_lag.labels(stream=stream, consumer=consumer_name).set(pending)
        self._lags[f"{stream}:{consumer_name}"] = pending

    def record_latency(self, stream: str, publish_time: float) -> None:
        latency = time.time() - publish_time
        consumer_lag_seconds.labels(stream=stream).observe(latency)

    @property
    def total_lag(self) -> int:
        return sum(self._lags.values())
