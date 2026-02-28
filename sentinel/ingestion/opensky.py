"""OpenSky Network ADS-B connector — aircraft position ingestion."""

from __future__ import annotations

from typing import Any, Optional

import aiohttp
import structlog

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.ingestion.base import BaseConnector

log = structlog.get_logger()

OPENSKY_API = "https://opensky-network.org/api/states/all"


class OpenSkyConnector(BaseConnector):
    """
    Polls OpenSky Network REST API for live ADS-B aircraft states.

    Rate limits:
      - Anonymous: 100 req/day (~1 every 15 min)
      - Registered: 1000 req/day (~1 every 90s)
      - With receiver: 8000 req/day (~1 every 10s)

    Fields: icao24, callsign, origin_country, lat, lon, baro_altitude,
            velocity, heading, vertical_rate, on_ground, etc.
    """

    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        super().__init__(bus, settings)
        self._session: Optional[aiohttp.ClientSession] = None
        self._auth: Optional[aiohttp.BasicAuth] = None
        if settings.opensky_username and settings.opensky_password:
            self._auth = aiohttp.BasicAuth(
                settings.opensky_username, settings.opensky_password
            )

    @property
    def name(self) -> str:
        return "opensky"

    @property
    def entity_type(self) -> str:
        return "aircraft"

    @property
    def poll_interval_s(self) -> float:
        return self._settings.opensky_poll_interval_s

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def fetch(self) -> Any:
        session = await self._get_session()
        try:
            async with session.get(OPENSKY_API, auth=self._auth) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    log.warning("opensky.rate_limited")
                    return None
                else:
                    log.warning("opensky.http_error", status=resp.status)
                    return None
        except aiohttp.ClientError as e:
            log.warning("opensky.connection_error", error=str(e))
            return None

    def transform(self, raw_data: Any) -> list[dict]:
        """
        Transform OpenSky state vector array into normalized dicts.

        OpenSky state vector format (index → field):
          0: icao24, 1: callsign, 2: origin_country,
          3: time_position, 4: last_contact,
          5: longitude, 6: latitude, 7: baro_altitude,
          8: on_ground, 9: velocity, 10: true_track,
          11: vertical_rate, 12: sensors, 13: geo_altitude,
          14: squawk, 15: spi, 16: position_source, 17: category
        """
        if not raw_data or "states" not in raw_data:
            return []

        timestamp = raw_data.get("time", 0)
        records = []

        for sv in raw_data["states"]:
            if sv[5] is None or sv[6] is None:
                continue  # Skip aircraft without position

            records.append({
                "source": "opensky",
                "entity_type": "aircraft",
                "source_id": sv[0],  # icao24
                "timestamp": timestamp,
                "latitude": sv[6],
                "longitude": sv[5],
                "altitude_m": sv[7],  # barometric altitude
                "geo_altitude_m": sv[13],
                "speed_mps": sv[9],
                "heading_deg": sv[10],  # true track
                "vertical_rate_mps": sv[11],
                "on_ground": sv[8],
                "callsign": (sv[1] or "").strip(),
                "origin_country": sv[2],
                "squawk": sv[14],
                "position_source": sv[16],
                "last_contact": sv[4],
            })

        return records
