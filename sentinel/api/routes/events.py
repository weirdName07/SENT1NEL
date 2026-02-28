"""Event query endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/events")
async def list_events(
    request: Request,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    since: Optional[str] = Query(None, description="ISO 8601 start time"),
    until: Optional[str] = Query(None, description="ISO 8601 end time"),
    limit: int = Query(100, ge=1, le=10000),
):
    """Query events with filters."""
    conditions = []
    params: list = []
    idx = 1

    if event_type:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type)
        idx += 1

    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1

    if entity_type:
        conditions.append(f"entity_type = ${idx}")
        params.append(entity_type)
        idx += 1

    if source_id:
        conditions.append(f"source_id = ${idx}")
        params.append(source_id)
        idx += 1

    if since:
        conditions.append(f"timestamp >= ${idx}::timestamptz")
        params.append(since)
        idx += 1

    if until:
        conditions.append(f"timestamp <= ${idx}::timestamptz")
        params.append(until)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)

    query = f"""
        SELECT id, event_type, severity, timestamp,
               entity_type, source_id, track_id,
               confidence, reason, metadata
        FROM events
        {where}
        ORDER BY timestamp DESC
        LIMIT ${idx}
    """

    async with request.app.state.db.pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    events = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        events.append(d)

    return {"count": len(events), "events": events}
