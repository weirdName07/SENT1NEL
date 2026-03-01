"""Async TimescaleDB client — batch inserts, spatial queries, replay, migrations."""

from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Optional

import asyncpg
import structlog

from sentinel.config import Settings
from sentinel.core.schemas import EntityState
from sentinel.observability.metrics import db_write_batch_size, db_write_latency

log = structlog.get_logger()

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class TimescaleStore:
    """
    Async TimescaleDB client with connection pooling.

    Supports batch entity inserts, spatial queries (PostGIS),
    historical replay, and migration management.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: Optional[asyncpg.Pool] = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("TimescaleStore not connected")
        return self._pool

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=self._settings.db_host,
            port=self._settings.db_port,
            user=self._settings.db_user,
            password=self._settings.db_password,
            database=self._settings.db_name,
            min_size=self._settings.db_pool_min,
            max_size=self._settings.db_pool_max,
        )
        log.info("timescaledb.connected", pool_max=self._settings.db_pool_max)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            log.info("timescaledb.closed")

    async def run_migrations(self) -> None:
        """Run SQL migration files in order.

        Each statement is executed outside a transaction block because
        TimescaleDB operations (create_hypertable, compression policies,
        continuous aggregates) cannot run inside transactions.
        """
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        async with self.pool.acquire() as conn:
            # Track applied migrations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            applied = {
                row["name"]
                for row in await conn.fetch("SELECT name FROM _migrations")
            }

        for f in migration_files:
            if f.name not in applied:
                sql = f.read_text()
                # Split into individual statements on semicolons
                raw_parts = sql.split(";")
                statements = []
                for part in raw_parts:
                    # Strip leading comment lines from each chunk
                    lines = part.strip().splitlines()
                    cleaned = "\n".join(
                        l for l in lines if not l.strip().startswith("--")
                    ).strip()
                    if cleaned:
                        statements.append(cleaned)

                async with self.pool.acquire() as conn:
                    # Exit implicit transaction so DDL can run
                    await conn.execute("COMMIT")
                    for stmt in statements:
                        try:
                            await conn.execute(stmt)
                        except Exception as e:
                            err_msg = str(e).lower()
                            if "already exists" in err_msg or "already a hypertable" in err_msg:
                                log.debug("migration.skip_existing", stmt=stmt[:60], reason=str(e))
                            else:
                                raise
                    await conn.execute(
                        "INSERT INTO _migrations (name) VALUES ($1)", f.name
                    )
                log.info("migration.applied", name=f.name)

    # ── Entity State Operations ───────────────────────────────

    async def insert_entities(self, entities: list[EntityState]) -> None:
        """Batch insert entity states into the hypertable."""
        if not entities:
            return

        t0 = time.monotonic()

        rows = [
            (
                str(e.entity_id),
                e.entity_type.value,
                e.source_id,
                e.source,
                e.position.to_wkt(),
                e.position.accuracy_m,
                e.velocity.speed_mps if e.velocity else None,
                e.velocity.heading_deg if e.velocity else None,
                e.velocity.vertical_rate_mps if e.velocity else None,
                e.timestamp,
                e.ingested_at,
                e.lifecycle.value,
                e.confidence,
                e.risk_score,
                str(e.track_id) if e.track_id else None,
                e.observation_count,
                e.anomalies if e.anomalies else None,
                json.dumps(e.metadata) if e.metadata else "{}",
                e.trace_id,
            )
            for e in entities
        ]

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO entity_states (
                    id, entity_type, source_id, source,
                    position, accuracy_m,
                    speed_mps, heading_deg, vertical_rate,
                    observed_at, ingested_at,
                    lifecycle, confidence, risk_score,
                    track_id, observation_count,
                    anomalies, metadata, trace_id
                ) VALUES (
                    $1::uuid, $2, $3, $4,
                    ST_GeomFromEWKT($5), $6,
                    $7, $8, $9,
                    $10, $11,
                    $12, $13, $14,
                    $15::uuid, $16,
                    $17, $18::jsonb, $19
                )
                """,
                rows,
            )

        elapsed = time.monotonic() - t0
        db_write_latency.observe(elapsed)
        db_write_batch_size.observe(len(entities))
        log.debug("db.entities_inserted", count=len(entities), elapsed_ms=elapsed * 1000)

    # ── Query Operations ──────────────────────────────────────

    async def query_entities(
        self,
        entity_type: Optional[str] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query entity states with optional filters."""
        conditions = []
        params: list = []
        idx = 1

        if entity_type:
            conditions.append(f"entity_type = ${idx}")
            params.append(entity_type)
            idx += 1

        if bbox:
            # bbox = (min_lon, min_lat, max_lon, max_lat)
            conditions.append(
                f"ST_Within(position, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
            )
            params.extend(bbox)
            idx += 4

        if since:
            conditions.append(f"observed_at >= ${idx}::timestamptz")
            params.append(since)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        params.append(limit)
        query = f"""
            SELECT id, entity_type, source_id, source,
                   ST_X(position) as lon, ST_Y(position) as lat,
                   ST_Z(position) as alt,
                   speed_mps, heading_deg, vertical_rate,
                   observed_at, ingested_at,
                   lifecycle, confidence, risk_score,
                   track_id, observation_count,
                   anomalies, metadata, trace_id
            FROM entity_states
            {where}
            ORDER BY observed_at DESC
            LIMIT ${idx}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def query_track(
        self,
        track_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get all observations for a specific track."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, entity_type, source_id, source,
                       ST_X(position) as lon, ST_Y(position) as lat,
                       ST_Z(position) as alt,
                       speed_mps, heading_deg, vertical_rate,
                       observed_at, lifecycle, confidence
                FROM entity_states
                WHERE track_id = $1::uuid
                ORDER BY observed_at ASC
                LIMIT $2
                """,
                track_id,
                limit,
            )
        return [dict(row) for row in rows]

    async def query_replay(
        self,
        start_time: str,
        end_time: str,
        entity_type: Optional[str] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        """Historical replay query — returns states within time range."""
        conditions = [
            "observed_at >= $1::timestamptz",
            "observed_at <= $2::timestamptz",
        ]
        params: list = [start_time, end_time]
        idx = 3

        if entity_type:
            conditions.append(f"entity_type = ${idx}")
            params.append(entity_type)
            idx += 1

        if bbox:
            conditions.append(
                f"ST_Within(position, ST_MakeEnvelope(${idx}, ${idx+1}, ${idx+2}, ${idx+3}, 4326))"
            )
            params.extend(bbox)
            idx += 4

        where = "WHERE " + " AND ".join(conditions)
        params.append(limit)

        query = f"""
            SELECT id, entity_type, source_id, source,
                   ST_X(position) as lon, ST_Y(position) as lat,
                   ST_Z(position) as alt,
                   speed_mps, heading_deg, observed_at,
                   lifecycle, confidence, track_id, metadata
            FROM entity_states
            {where}
            ORDER BY observed_at ASC
            LIMIT ${idx}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    # ── Health Check ──────────────────────────────────────────

    async def is_healthy(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False
