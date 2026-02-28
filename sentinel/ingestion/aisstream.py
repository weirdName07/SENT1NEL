"""aisstream.io AIS marine connector — WebSocket push-based vessel tracking."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import orjson
import structlog
import websockets

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.core.constants import SUBJECT_RAW
from sentinel.ingestion.base import StreamConnector
from sentinel.observability.metrics import ingested_total, ingestion_errors

log = structlog.get_logger()

AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"


class AISStreamConnector(StreamConnector):
    """
    Push-based AIS marine vessel connector via aisstream.io WebSocket.

    Streams real-time AIS position reports for vessels worldwide.
    Requires a free API key from aisstream.io.
    """

    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        super().__init__(bus, settings)
        self._api_key = settings.aisstream_api_key

    @property
    def name(self) -> str:
        return "aisstream"

    @property
    def entity_type(self) -> str:
        return "vessel"

    async def stream(self) -> None:
        if not self._api_key:
            log.warning("aisstream.no_api_key", msg="Skipping AIS — no API key configured")
            await asyncio.sleep(3600)  # Sleep and retry
            return

        subject = SUBJECT_RAW.format(source=self.name)

        # Subscription message — global coverage
        subscribe_msg = orjson.dumps({
            "APIKey": self._api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],  # Global
            "FiltersShipMMSI": [],
            "FilterMessageTypes": ["PositionReport"],
        })

        async with websockets.connect(
            AISSTREAM_WS_URL,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
            max_size=2**20,
        ) as ws:
            await ws.send(subscribe_msg)
            log.info("aisstream.connected")

            async for raw_msg in ws:
                try:
                    msg = orjson.loads(raw_msg)
                    record = self._transform_message(msg)
                    if record:
                        payload = orjson.dumps(record)
                        await self._bus.publish(subject, payload)
                        ingested_total.labels(
                            source=self.name, entity_type=self.entity_type
                        ).inc()
                except Exception:
                    ingestion_errors.labels(
                        source=self.name, error_type="parse_error"
                    ).inc()

    def _transform_message(self, msg: dict) -> Optional[dict]:
        """Transform AIS position report into normalized dict."""
        msg_type = msg.get("MessageType")
        if msg_type != "PositionReport":
            return None

        meta = msg.get("MetaData", {})
        position = msg.get("Message", {}).get("PositionReport", {})

        if not position:
            return None

        mmsi = str(meta.get("MMSI", ""))
        if not mmsi:
            return None

        lat = position.get("Latitude")
        lon = position.get("Longitude")
        if lat is None or lon is None:
            return None

        return {
            "source": "aisstream",
            "entity_type": "vessel",
            "source_id": mmsi,
            "timestamp": time.time(),
            "latitude": lat,
            "longitude": lon,
            "altitude_m": 0,  # Sea level
            "speed_mps": (position.get("Sog", 0) or 0) * 0.5144,  # knots → m/s
            "heading_deg": position.get("TrueHeading"),
            "cog": position.get("Cog"),
            "nav_status": position.get("NavigationalStatus"),
            "rot": position.get("RateOfTurn"),
            "name": meta.get("ShipName", "").strip(),
            "ship_type": meta.get("ShipType"),
            "mmsi": mmsi,
            "time_utc": meta.get("time_utc"),
        }
