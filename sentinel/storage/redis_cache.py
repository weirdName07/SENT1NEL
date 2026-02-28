"""Redis hot-state cache — latest entity positions with geo-indexing."""

from __future__ import annotations

from typing import Any, Optional

import orjson
import redis.asyncio as redis
import structlog

from sentinel.core.constants import REDIS_ENTITY_PREFIX, REDIS_GEO_KEY
from sentinel.core.schemas import EntityState

log = structlog.get_logger()


class RedisCache:
    """
    Redis hot-state manager.

    Stores the latest entity states with geographic indexing via GEOADD/GEOSEARCH.
    Handles scan, hset, hgetall, geo operations, and pub/sub for WebSocket fan-out.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._redis: Optional[redis.Redis] = None

    @property
    def r(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("RedisCache not connected")
        return self._redis

    async def connect(self) -> None:
        self._redis = redis.from_url(
            self._url,
            decode_responses=False,
            max_connections=50,
        )
        await self._redis.ping()
        log.info("redis.connected", url=self._url)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            log.info("redis.closed")

    # ── Entity Hot State ──────────────────────────────────────

    async def set_entity(self, entity: EntityState) -> None:
        """Store latest entity state and update geo index."""
        key = f"{REDIS_ENTITY_PREFIX}{entity.entity_key}"
        data = entity.serialize()

        pipe = self.r.pipeline()
        pipe.set(key, data, ex=86400)  # 24h TTL

        # Geo index per entity type and global
        geo_key = REDIS_GEO_KEY.format(entity_type=entity.entity_type.value)
        pipe.geoadd(
            geo_key,
            (entity.position.longitude, entity.position.latitude, entity.entity_key),
        )

        await pipe.execute()

    async def get_entity(self, entity_key: str) -> Optional[EntityState]:
        """Retrieve an entity by its key (source_id:entity_type)."""
        data = await self.r.get(f"{REDIS_ENTITY_PREFIX}{entity_key}")
        if data:
            return EntityState.deserialize(data)
        return None

    async def get_entities_in_bbox(
        self,
        entity_type: str,
        lon: float,
        lat: float,
        radius_km: float,
        count: int = 100,
    ) -> list[str]:
        """Get entity keys within radius of a point using GEOSEARCH."""
        geo_key = REDIS_GEO_KEY.format(entity_type=entity_type)
        results = await self.r.geosearch(
            geo_key,
            longitude=lon,
            latitude=lat,
            radius=radius_km,
            unit="km",
            count=count,
            sort="ASC",
        )
        return [r.decode() if isinstance(r, bytes) else r for r in results]

    # ── Generic Hash Operations ───────────────────────────────

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        await self.r.hset(key, mapping=mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        data = await self.r.hgetall(key)
        return {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }

    async def delete(self, key: str) -> None:
        await self.r.delete(key)

    async def scan_prefix(self, prefix: str) -> list[str]:
        """Scan keys matching a prefix. Use sparingly."""
        keys = []
        async for key in self.r.scan_iter(match=f"{prefix}*", count=1000):
            keys.append(key.decode() if isinstance(key, bytes) else key)
        return keys

    async def geo_remove(self, entity_type: str, member: str) -> None:
        geo_key = REDIS_GEO_KEY.format(entity_type=entity_type)
        await self.r.zrem(geo_key, member)

    # ── Pub/Sub for WebSocket fan-out ─────────────────────────

    async def publish(self, channel: str, data: bytes) -> None:
        await self.r.publish(channel, data)

    # ── Health Check ──────────────────────────────────────────

    async def is_healthy(self) -> bool:
        try:
            return await self.r.ping()
        except Exception:
            return False
