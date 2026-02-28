"""Entity query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/entities")
async def list_entities(
    request: Request,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    min_lon: Optional[float] = Query(None, description="Bounding box min longitude"),
    min_lat: Optional[float] = Query(None, description="Bounding box min latitude"),
    max_lon: Optional[float] = Query(None, description="Bounding box max longitude"),
    max_lat: Optional[float] = Query(None, description="Bounding box max latitude"),
    since: Optional[str] = Query(None, description="ISO 8601 timestamp — only return newer"),
    limit: int = Query(100, ge=1, le=10000),
):
    """Query entity states with spatial and temporal filters."""
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    rows = await request.app.state.db.query_entities(
        entity_type=entity_type,
        bbox=bbox,
        since=since,
        limit=limit,
    )

    return {
        "count": len(rows),
        "entities": _serialize_rows(rows),
    }


@router.get("/entities/{source_id}/track")
async def get_track(
    request: Request,
    source_id: str,
    limit: int = Query(1000, ge=1, le=10000),
):
    """Get all historical observations for an entity track."""
    # Look up track_id from latest entity state
    rows = await request.app.state.db.query_entities(
        entity_type=None,
        limit=1,
    )
    # For MVP, query by source_id directly
    async with request.app.state.db.pool.acquire() as conn:
        track_rows = await conn.fetch(
            """
            SELECT id, entity_type, source_id,
                   ST_X(position) as lon, ST_Y(position) as lat,
                   ST_Z(position) as alt,
                   speed_mps, heading_deg, observed_at,
                   lifecycle, confidence, track_id
            FROM entity_states
            WHERE source_id = $1
            ORDER BY observed_at ASC
            LIMIT $2
            """,
            source_id,
            limit,
        )

    return {
        "source_id": source_id,
        "count": len(track_rows),
        "track": _serialize_rows([dict(r) for r in track_rows]),
    }


@router.get("/entities/live")
async def live_entities(
    request: Request,
    entity_type: Optional[str] = Query(None),
    lon: float = Query(0, description="Center longitude"),
    lat: float = Query(0, description="Center latitude"),
    radius_km: float = Query(500, ge=1, le=20000),
    count: int = Query(100, ge=1, le=1000),
):
    """Get live entities from Redis hot cache within radius."""
    cache = request.app.state.cache
    if entity_type:
        keys = await cache.get_entities_in_bbox(entity_type, lon, lat, radius_km, count)
    else:
        keys = []
        for etype in ("aircraft", "vessel", "satellite", "weather"):
            etype_keys = await cache.get_entities_in_bbox(etype, lon, lat, radius_km, count // 4)
            keys.extend(etype_keys)

    entities = []
    for key in keys[:count]:
        entity = await cache.get_entity(key)
        if entity:
            entities.append(entity.model_dump(mode="json"))

    return {
        "count": len(entities),
        "entities": entities,
    }


def _serialize_rows(rows: list[dict]) -> list[dict]:
    """Convert asyncpg rows to JSON-safe dicts."""
    result = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                clean[k] = v.isoformat()
            elif isinstance(v, bytes):
                clean[k] = v.decode()
            else:
                clean[k] = v
        result.append(clean)
    return result
