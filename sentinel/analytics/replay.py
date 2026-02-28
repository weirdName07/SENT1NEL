"""Historical replay engine — time-range playback with speed control."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

import structlog

from sentinel.storage.timescale import TimescaleStore

log = structlog.get_logger()


class ReplayEngine:
    """
    Historical replay engine.

    Queries TimescaleDB for entity states within a time range
    and streams them back at configurable playback speed.
    """

    def __init__(self, db: TimescaleStore) -> None:
        self._db = db

    async def query(
        self,
        start_time: str,
        end_time: str,
        entity_type: Optional[str] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        """Query historical entity states."""
        return await self._db.query_replay(
            start_time=start_time,
            end_time=end_time,
            entity_type=entity_type,
            bbox=bbox,
            limit=limit,
        )

    async def stream(
        self,
        start_time: str,
        end_time: str,
        speed: float = 1.0,
        entity_type: Optional[str] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream historical states in time order with playback speed control.

        speed=1.0: real-time
        speed=10.0: 10x faster
        speed=0.1: 10x slower
        """
        rows = await self.query(
            start_time=start_time,
            end_time=end_time,
            entity_type=entity_type,
            bbox=bbox,
        )

        if not rows:
            return

        prev_time = None
        for row in rows:
            obs_time = row.get("observed_at")
            if prev_time and obs_time and speed > 0:
                delta = (obs_time - prev_time).total_seconds()
                if delta > 0:
                    wait = delta / speed
                    # Cap wait to 5 seconds max to prevent long pauses
                    wait = min(wait, 5.0)
                    await asyncio.sleep(wait)

            prev_time = obs_time
            yield row
