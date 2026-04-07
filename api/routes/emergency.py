"""
api/routes/emergency.py

Emergency Response API
───────────────────────
POST /api/emergency/activate    Activate corridor
GET  /api/emergency/active      Current emergency status
POST /api/emergency/deactivate  Clear emergency
GET  /api/emergency/history     Past incidents
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.state_store import store

router = APIRouter()

# In-memory incident history (persisted to DB in production)
incident_history: list = []


class EmergencyReq(BaseModel):
    emergency_type: str   # ambulance | fire | vip | lockdown
    origin:         Optional[str] = None
    destination:    Optional[str] = None
    vehicle_id:     Optional[str] = None
    notes:          Optional[str] = None


@router.post("/activate")
async def activate_emergency(req: EmergencyReq):
    """
    Activate an emergency corridor.

    ambulance: Clears SIG-A01, SIG-A02, SIG-C22, SIG-C05 to GREEN
    fire:      Clears SIG-D03, SIG-D11, SIG-A14
    vip:       Synchronises SIG-B07, SIG-B12, SIG-E08, SIG-F02
    lockdown:  Sets ALL 12 signals to RED HOLD
    """
    etype = req.emergency_type.lower()
    if etype not in ("ambulance", "fire", "vip", "lockdown"):
        raise HTTPException(400, f"Unknown emergency type: {etype}")

    incident = store.activate_emergency(
        etype, req.origin, req.destination, req.vehicle_id, req.notes
    )
    incident_history.insert(0, incident)

    await store.broadcast({
        "type":    "emergency",
        "payload": incident,
    })
    return incident


@router.get("/active")
async def get_active():
    if not store.emergency:
        return {"status": "none", "message": "No active emergency"}
    return store.emergency


@router.post("/deactivate")
async def deactivate_emergency():
    if not store.emergency:
        raise HTTPException(400, "No active emergency to deactivate")
    result = store.clear_emergency()
    await store.broadcast({
        "type":    "emergency_cleared",
        "payload": result,
    })
    return result


@router.get("/history")
async def get_history(limit: int = 20):
    return {
        "incidents": incident_history[:limit],
        "total":     len(incident_history),
    }
