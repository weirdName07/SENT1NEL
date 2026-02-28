"""Geofence CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class GeofenceCreate(BaseModel):
    name: str
    geometry_wkt: str  # e.g. "POLYGON((-74 40, -73 40, -73 41, -74 41, -74 40))"
    description: str = ""
    entity_types: Optional[list[str]] = None
    alert_on: Optional[list[str]] = None


@router.post("/geofences")
async def create_geofence(request: Request, body: GeofenceCreate):
    """Create a new geofence zone."""
    from sentinel.analytics.geofence import GeofenceEngine

    engine = GeofenceEngine(request.app.state.db)
    result = await engine.create_geofence(
        name=body.name,
        geometry_wkt=body.geometry_wkt,
        description=body.description,
        entity_types=body.entity_types,
        alert_on=body.alert_on,
    )
    # Serialize datetime fields
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


@router.get("/geofences")
async def list_geofences(request: Request):
    """List all geofence zones."""
    from sentinel.analytics.geofence import GeofenceEngine

    engine = GeofenceEngine(request.app.state.db)
    fences = await engine.list_geofences()
    for f in fences:
        for k, v in f.items():
            if hasattr(v, "isoformat"):
                f[k] = v.isoformat()
    return {"count": len(fences), "geofences": fences}
