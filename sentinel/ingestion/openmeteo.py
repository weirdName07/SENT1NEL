"""Open-Meteo weather connector — global weather grid ingestion."""

from __future__ import annotations

import time
from typing import Any, Optional

import aiohttp
import structlog

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.ingestion.base import BaseConnector

log = structlog.get_logger()

# Open-Meteo current weather for a grid of points
# Free, no API key, generous rate limits
OPENMETEO_API = "https://api.open-meteo.com/v1/forecast"

# Sample grid: major cities / strategic points worldwide
GRID_POINTS = [
    (40.7128, -74.0060, "New York"),
    (51.5074, -0.1278, "London"),
    (48.8566, 2.3522, "Paris"),
    (35.6762, 139.6503, "Tokyo"),
    (28.6139, 77.2090, "Delhi"),
    (-33.8688, 151.2093, "Sydney"),
    (55.7558, 37.6173, "Moscow"),
    (39.9042, 116.4074, "Beijing"),
    (-23.5505, -46.6333, "São Paulo"),
    (1.3521, 103.8198, "Singapore"),
    (25.2048, 55.2708, "Dubai"),
    (30.0444, 31.2357, "Cairo"),
    (37.7749, -122.4194, "San Francisco"),
    (34.0522, -118.2437, "Los Angeles"),
    (-1.2921, 36.8219, "Nairobi"),
    (41.0082, 28.9784, "Istanbul"),
    (22.3193, 114.1694, "Hong Kong"),
    (13.7563, 100.5018, "Bangkok"),
    (59.3293, 18.0686, "Stockholm"),
    (-34.6037, -58.3816, "Buenos Aires"),
]


class OpenMeteoConnector(BaseConnector):
    """
    Polls Open-Meteo API for current weather conditions at a grid of points.

    Free tier: generous rate limits, no API key required.
    """

    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        super().__init__(bus, settings)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "openmeteo"

    @property
    def entity_type(self) -> str:
        return "weather"

    @property
    def poll_interval_s(self) -> float:
        return self._settings.openmeteo_poll_interval_s

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def fetch(self) -> Any:
        """Fetch current weather for all grid points (batched request)."""
        session = await self._get_session()
        lats = ",".join(str(p[0]) for p in GRID_POINTS)
        lons = ",".join(str(p[1]) for p in GRID_POINTS)

        params = {
            "latitude": lats,
            "longitude": lons,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,weather_code",
            "wind_speed_unit": "ms",
        }

        try:
            async with session.get(OPENMETEO_API, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                log.warning("openmeteo.http_error", status=resp.status)
                return None
        except aiohttp.ClientError as e:
            log.warning("openmeteo.connection_error", error=str(e))
            return None

    def transform(self, raw_data: Any) -> list[dict]:
        """Transform Open-Meteo response into weather entity records."""
        if not raw_data:
            return []

        records = []
        now = time.time()

        # Open-Meteo returns array for batch requests
        data_list = raw_data if isinstance(raw_data, list) else [raw_data]

        for idx, data in enumerate(data_list):
            if idx >= len(GRID_POINTS):
                break

            current = data.get("current", {})
            lat, lon, location_name = GRID_POINTS[idx]

            records.append({
                "source": "openmeteo",
                "entity_type": "weather",
                "source_id": f"wx_{location_name.lower().replace(' ', '_')}",
                "timestamp": now,
                "latitude": lat,
                "longitude": lon,
                "altitude_m": data.get("elevation"),
                "temperature_c": current.get("temperature_2m"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "wind_speed_mps": current.get("wind_speed_10m"),
                "wind_direction_deg": current.get("wind_direction_10m"),
                "precipitation_mm": current.get("precipitation"),
                "weather_code": current.get("weather_code"),
                "location_name": location_name,
            })

        return records
