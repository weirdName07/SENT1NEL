"""USGS Earthquake connector — real-time GeoJSON feed ingestion."""

from __future__ import annotations

from typing import Any, Optional

import aiohttp
import structlog

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.ingestion.base import BaseConnector

log = structlog.get_logger()

# Past hour, all magnitudes — updates every ~60s
USGS_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"


class USGSConnector(BaseConnector):
    """
    Polls USGS earthquake GeoJSON summary feed.

    Returns all earthquakes from the past hour, updated every ~60 seconds.
    No rate limit. No authentication required.
    """

    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        super().__init__(bus, settings)
        self._session: Optional[aiohttp.ClientSession] = None
        self._seen_ids: set[str] = set()  # Dedup within polling window

    @property
    def name(self) -> str:
        return "usgs"

    @property
    def entity_type(self) -> str:
        return "earthquake"

    @property
    def poll_interval_s(self) -> float:
        return self._settings.usgs_poll_interval_s

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def fetch(self) -> Any:
        session = await self._get_session()
        try:
            async with session.get(USGS_FEED) as resp:
                if resp.status == 200:
                    return await resp.json()
                log.warning("usgs.http_error", status=resp.status)
                return None
        except aiohttp.ClientError as e:
            log.warning("usgs.connection_error", error=str(e))
            return None

    def transform(self, raw_data: Any) -> list[dict]:
        """
        Transform USGS GeoJSON FeatureCollection into records.

        GeoJSON Feature properties include:
          mag, place, time, updated, tz, url, detail, felt,
          cdi, mmi, alert, status, tsunami, sig, net, code, etc.
        """
        if not raw_data or "features" not in raw_data:
            return []

        records = []
        for feature in raw_data["features"]:
            eq_id = feature.get("id", "")
            if eq_id in self._seen_ids:
                continue

            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [0, 0, 0])

            records.append({
                "source": "usgs",
                "entity_type": "earthquake",
                "source_id": eq_id,
                "timestamp": props.get("time", 0) / 1000,  # ms → s
                "longitude": coords[0],
                "latitude": coords[1],
                "altitude_m": -coords[2] * 1000 if len(coords) > 2 else None,  # depth km → m (negative)
                "magnitude": props.get("mag"),
                "place": props.get("place"),
                "felt": props.get("felt"),
                "significance": props.get("sig"),
                "tsunami": props.get("tsunami"),
                "alert": props.get("alert"),
                "status": props.get("status"),
                "mag_type": props.get("magType"),
                "url": props.get("url"),
            })
            self._seen_ids.add(eq_id)

        # Trim seen_ids to prevent unbounded growth
        if len(self._seen_ids) > 10000:
            self._seen_ids = set(list(self._seen_ids)[-5000:])

        return records
