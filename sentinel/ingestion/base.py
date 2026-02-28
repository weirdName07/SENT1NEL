"""Base connector ABC — interface contract for all data source adapters."""

from __future__ import annotations

import abc
import asyncio
from typing import Any

import structlog

from sentinel.config import Settings
from sentinel.core.backpressure import RateLimiter
from sentinel.core.bus import MessageBus
from sentinel.core.constants import SUBJECT_RAW
from sentinel.observability.metrics import ingested_total, ingestion_errors, ingestion_latency

log = structlog.get_logger()


class BaseConnector(abc.ABC):
    """
    Abstract base class for OSINT data source connectors.

    Subclasses must implement:
      - name: str property (e.g. "opensky")
      - entity_type: str property (e.g. "aircraft")
      - poll_interval_s: float property
      - fetch(): async method that retrieves raw data from source
      - transform(raw_data): method that yields raw dicts for NATS publishing

    The base class handles the run loop, rate limiting, error handling,
    and publishing to NATS.
    """

    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        self._bus = bus
        self._settings = settings
        self._rate_limiter = RateLimiter(self.poll_interval_s)

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Source identifier, e.g. 'opensky'."""
        ...

    @property
    @abc.abstractmethod
    def entity_type(self) -> str:
        """Entity type this connector produces, e.g. 'aircraft'."""
        ...

    @property
    @abc.abstractmethod
    def poll_interval_s(self) -> float:
        """Minimum interval between polls in seconds."""
        ...

    @abc.abstractmethod
    async def fetch(self) -> Any:
        """Fetch raw data from the upstream source. Returns source-specific data."""
        ...

    @abc.abstractmethod
    def transform(self, raw_data: Any) -> list[dict]:
        """
        Transform raw source data into a list of dicts for NATS publishing.
        Each dict should contain the raw fields from the source.
        """
        ...

    async def run(self) -> None:
        """Main connector loop — fetch → transform → publish, with rate limiting."""
        subject = SUBJECT_RAW.format(source=self.name)
        log.info("connector.started", name=self.name, interval_s=self.poll_interval_s)

        while True:
            try:
                await self._rate_limiter.wait()

                import time
                t0 = time.monotonic()

                raw_data = await self.fetch()

                if raw_data is None:
                    continue

                records = self.transform(raw_data)

                for record in records:
                    import orjson
                    payload = orjson.dumps(record)
                    await self._bus.publish(subject, payload)

                elapsed = time.monotonic() - t0
                ingestion_latency.labels(source=self.name).observe(elapsed)
                ingested_total.labels(
                    source=self.name, entity_type=self.entity_type
                ).inc(len(records))

                log.debug(
                    "connector.poll_complete",
                    name=self.name,
                    records=len(records),
                    elapsed_ms=elapsed * 1000,
                )

            except asyncio.CancelledError:
                log.info("connector.stopped", name=self.name)
                raise
            except Exception as e:
                ingestion_errors.labels(
                    source=self.name, error_type=type(e).__name__
                ).inc()
                log.exception("connector.error", name=self.name)
                await asyncio.sleep(5)  # Back off on error


class StreamConnector(BaseConnector):
    """
    Base class for push-based (WebSocket) connectors.

    Subclasses must implement stream() instead of fetch()/transform().
    """

    @property
    def poll_interval_s(self) -> float:
        return 0  # Not used for push-based connectors

    async def fetch(self) -> Any:
        raise NotImplementedError("StreamConnectors use stream(), not fetch()")

    def transform(self, raw_data: Any) -> list[dict]:
        raise NotImplementedError("StreamConnectors use stream(), not transform()")

    @abc.abstractmethod
    async def stream(self) -> None:
        """Connect to upstream WebSocket and process messages."""
        ...

    async def run(self) -> None:
        """Override run for push-based streaming."""
        log.info("stream_connector.started", name=self.name)
        while True:
            try:
                await self.stream()
            except asyncio.CancelledError:
                log.info("stream_connector.stopped", name=self.name)
                raise
            except Exception:
                ingestion_errors.labels(
                    source=self.name, error_type="stream_disconnect"
                ).inc()
                log.exception("stream_connector.reconnecting", name=self.name)
                await asyncio.sleep(5)
