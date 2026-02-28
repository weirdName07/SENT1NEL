"""WebSocket endpoints for real-time entity and event streaming."""

from __future__ import annotations

import asyncio

import orjson
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

router = APIRouter()

log = structlog.get_logger()


@router.websocket("/ws/entities")
async def ws_entities(
    websocket: WebSocket,
    entity_type: Optional[str] = Query(None),
    interval_ms: int = Query(1000, ge=100, le=30000),
):
    """
    WebSocket stream of live entity states from Redis.

    Pushes current entity positions at the specified interval.
    Filter by entity_type if provided.
    """
    await websocket.accept()
    log.info("ws.entities.connected", entity_type=entity_type)

    try:
        while True:
            cache = websocket.app.state.cache
            entities = []

            # Get all entity types or specific type
            types = [entity_type] if entity_type else ["aircraft", "vessel", "satellite", "weather"]

            for etype in types:
                keys = await cache.get_entities_in_bbox(etype, 0, 0, 20000, 500)
                for key in keys:
                    entity = await cache.get_entity(key)
                    if entity:
                        entities.append(entity.model_dump(mode="json"))

            await websocket.send_bytes(orjson.dumps({
                "type": "entities",
                "count": len(entities),
                "data": entities,
            }))

            await asyncio.sleep(interval_ms / 1000)

    except WebSocketDisconnect:
        log.info("ws.entities.disconnected")
    except Exception:
        log.exception("ws.entities.error")


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """
    WebSocket stream of real-time events.

    Subscribes to Redis pub/sub channel for events and forwards to client.
    """
    await websocket.accept()
    log.info("ws.events.connected")

    try:
        cache = websocket.app.state.cache
        pubsub = cache.r.pubsub()
        await pubsub.subscribe("sentinel:events")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                await websocket.send_bytes(message["data"])
            else:
                await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        log.info("ws.events.disconnected")
    except Exception:
        log.exception("ws.events.error")
    finally:
        await pubsub.unsubscribe("sentinel:events")
