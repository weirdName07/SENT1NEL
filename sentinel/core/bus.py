"""NATS JetStream message bus wrapper with stream/consumer management."""

from __future__ import annotations

from typing import Any, Callable, Optional

import nats
import structlog
from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.api import (
    AckPolicy,
    ConsumerConfig,
    DeliverPolicy,
    DiscardPolicy,
    RetentionPolicy,
    StreamConfig,
)

from sentinel.core.constants import (
    STREAM_EVENTS,
    STREAM_PROCESSED,
    STREAM_RAW,
    SUBJECT_EVENTS_ALL,
    SUBJECT_PROCESSED_ALL,
    SUBJECT_RAW_ALL,
)

log = structlog.get_logger()


class MessageBus:
    """
    NATS JetStream wrapper.

    Manages streams, consumers, publishing, and subscribing
    with built-in backpressure configuration.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._nc: Optional[Client] = None
        self._js: Optional[JetStreamContext] = None

    @property
    def js(self) -> JetStreamContext:
        if self._js is None:
            raise RuntimeError("MessageBus not connected")
        return self._js

    @property
    def nc(self) -> Client:
        if self._nc is None:
            raise RuntimeError("MessageBus not connected")
        return self._nc

    async def connect(self) -> None:
        """Connect to NATS and provision JetStream streams."""
        self._nc = await nats.connect(
            self._url,
            error_cb=self._on_error,
            disconnected_cb=self._on_disconnect,
            reconnected_cb=self._on_reconnect,
            max_reconnect_attempts=-1,  # infinite reconnect
        )
        self._js = self._nc.jetstream()
        log.info("nats.connected", url=self._url)

        # Provision streams
        await self._ensure_streams()

    async def _ensure_streams(self) -> None:
        """Create or update JetStream streams."""
        streams = [
            StreamConfig(
                name=STREAM_RAW,
                subjects=[SUBJECT_RAW_ALL],
                retention=RetentionPolicy.LIMITS,
                max_msgs_per_subject=10_000,
                max_bytes=1_073_741_824,  # 1 GB
                discard=DiscardPolicy.OLD,
                max_age=3600,  # 1 hour in seconds
                storage="file",
            ),
            StreamConfig(
                name=STREAM_PROCESSED,
                subjects=[SUBJECT_PROCESSED_ALL],
                retention=RetentionPolicy.LIMITS,
                max_msgs_per_subject=10_000,
                max_bytes=1_073_741_824,
                discard=DiscardPolicy.OLD,
                max_age=3600,  # 1 hour in seconds
                storage="file",
            ),
            StreamConfig(
                name=STREAM_EVENTS,
                subjects=[SUBJECT_EVENTS_ALL],
                retention=RetentionPolicy.LIMITS,
                max_msgs_per_subject=50_000,
                max_bytes=2_147_483_648,  # 2 GB — events are important
                discard=DiscardPolicy.OLD,
                max_age=86400,  # 24 hours in seconds
                storage="file",
            ),
        ]
        for cfg in streams:
            try:
                await self._js.stream_info(cfg.name)
                await self._js.update_stream(cfg)
                log.info("nats.stream.updated", stream=cfg.name)
            except nats.js.errors.NotFoundError:
                await self._js.add_stream(cfg)
                log.info("nats.stream.created", stream=cfg.name)

    async def publish(self, subject: str, data: bytes) -> None:
        """Publish a message to a JetStream subject."""
        await self.js.publish(subject, data)

    async def subscribe(
        self,
        subject: str,
        stream: str,
        consumer_name: str,
        handler: Callable,
        max_ack_pending: int = 1000,
        batch_size: int = 1,
    ) -> Any:
        """
        Create a pull subscriber with backpressure controls.

        Returns the subscription for the caller to manage.
        """
        config = ConsumerConfig(
            durable_name=consumer_name,
            ack_policy=AckPolicy.EXPLICIT,
            deliver_policy=DeliverPolicy.ALL,
            max_ack_pending=max_ack_pending,
            max_deliver=3,
            ack_wait=30,
            filter_subject=subject,
        )
        try:
            sub = await self.js.pull_subscribe(
                subject,
                durable=consumer_name,
                stream=stream,
                config=config,
            )
        except Exception:
            # Consumer may already exist — subscribe to existing
            sub = await self.js.pull_subscribe(
                subject,
                durable=consumer_name,
                stream=stream,
            )
        log.info(
            "nats.consumer.created",
            stream=stream,
            consumer=consumer_name,
            subject=subject,
        )
        return sub

    async def close(self) -> None:
        """Gracefully close NATS connection."""
        if self._nc and self._nc.is_connected:
            await self._nc.drain()
            log.info("nats.closed")

    # ── Callbacks ─────────────────────────────────────────────

    @staticmethod
    async def _on_error(e: Exception) -> None:
        log.error("nats.error", error=str(e))

    @staticmethod
    async def _on_disconnect() -> None:
        log.warning("nats.disconnected")

    @staticmethod
    async def _on_reconnect() -> None:
        log.info("nats.reconnected")
