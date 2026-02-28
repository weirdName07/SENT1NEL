"""CelesTrak satellite TLE connector with SGP4 position propagation."""

from __future__ import annotations

import time as time_mod
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp
import structlog
from sgp4.api import Satrec, jday

from sentinel.config import Settings
from sentinel.core.bus import MessageBus
from sentinel.ingestion.base import BaseConnector

log = structlog.get_logger()

# Active satellites TLE set — reasonable subset for MVP
CELESTRAK_URLS = [
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
]


class CelesTrakConnector(BaseConnector):
    """
    Fetches TLE data from CelesTrak and propagates satellite positions
    to the current time using SGP4.

    TLEs are updated ~hourly on CelesTrak. SGP4 propagates positions
    to the current epoch for each satellite.
    """

    def __init__(self, bus: MessageBus, settings: Settings) -> None:
        super().__init__(bus, settings)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "celestrak"

    @property
    def entity_type(self) -> str:
        return "satellite"

    @property
    def poll_interval_s(self) -> float:
        return self._settings.celestrak_poll_interval_s

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )
        return self._session

    async def fetch(self) -> Any:
        """Fetch TLE text from CelesTrak."""
        session = await self._get_session()
        all_lines = []
        for url in CELESTRAK_URLS:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        all_lines.extend(text.strip().split("\n"))
                    else:
                        log.warning("celestrak.http_error", status=resp.status, url=url)
            except aiohttp.ClientError as e:
                log.warning("celestrak.connection_error", error=str(e))
        return all_lines if all_lines else None

    def transform(self, raw_data: Any) -> list[dict]:
        """
        Parse TLE lines into groups of 3 (name, line1, line2),
        propagate each satellite position to current time via SGP4.
        """
        lines = [l.strip() for l in raw_data if l.strip()]
        records = []

        now = datetime.now(timezone.utc)
        jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)

        i = 0
        while i + 2 < len(lines):
            # TLE format: name line, then line 1, then line 2
            name_line = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]

            # Validate TLE lines start with 1 and 2
            if not line1.startswith("1 ") or not line2.startswith("2 "):
                i += 1
                continue

            i += 3

            try:
                sat = Satrec.twoline2rv(line1, line2)
                norad_id = str(sat.satnum)

                # Propagate to current time
                e, r, v = sat.sgp4(jd, fr)
                if e != 0:
                    continue  # SGP4 error, skip

                # r = position in km (TEME frame), v = velocity in km/s
                # Convert TEME to lat/lon/alt (simplified — good enough for tracking)
                x, y, z = r
                import math
                lon = math.degrees(math.atan2(y, x))
                lat = math.degrees(math.atan2(z, math.sqrt(x**2 + y**2)))
                alt_km = math.sqrt(x**2 + y**2 + z**2) - 6371.0  # approximate

                vx, vy, vz = v
                speed_kms = math.sqrt(vx**2 + vy**2 + vz**2)

                # Adjust longitude for Earth rotation
                # Greenwich Sidereal Time (approximate)
                j2000 = 2451545.0
                d = (jd + fr) - j2000
                gmst = 280.46061837 + 360.98564736629 * d
                gmst = gmst % 360
                lon = (lon - gmst) % 360
                if lon > 180:
                    lon -= 360

                records.append({
                    "source": "celestrak",
                    "entity_type": "satellite",
                    "source_id": norad_id,
                    "timestamp": time_mod.time(),
                    "latitude": lat,
                    "longitude": lon,
                    "altitude_m": alt_km * 1000,
                    "speed_mps": speed_kms * 1000,
                    "name": name_line.strip(),
                    "norad_id": norad_id,
                    "tle_line1": line1,
                    "tle_line2": line2,
                    "tle_epoch": sat.jdsatepoch + sat.jdsatepochF,
                })

            except Exception:
                continue  # Skip malformed TLEs

        log.debug("celestrak.propagated", satellites=len(records))
        return records
