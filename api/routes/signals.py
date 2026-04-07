from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from services.state_store import store
from services.llm_engine import generate_signal_optimisation

router = APIRouter()

class SignalUpdateBody(BaseModel):
    green_s: int = Field(ge=10, le=120)
    reason:  Optional[str] = None

class BulkUpdate(BaseModel):
    updates: List[dict]

@router.get("/")
async def list_signals(zone_id: str = None):
    sigs = list(store.signals.values())
    if zone_id:
        sigs = [s for s in sigs if s["zone_id"] == zone_id.upper()]
    adp = sum(1 for s in sigs if s["adaptive"])
    return {"signals": sigs, "total": len(sigs), "adaptive": adp}

@router.get("/optimize")
async def optimize_signals():
    recommendations = await generate_signal_optimisation()
    return {
        "recommendations": recommendations,
        "computed_at":     datetime.now(timezone.utc).isoformat(),
        "apply_url":       "POST /api/signals/bulk-update",
    }

@router.post("/bulk-update")
async def bulk_update(body: BulkUpdate):
    results = []
    for upd in body.updates:
        sid = upd.get("signal_id", "").upper()
        s   = store.signals.get(sid)
        if s:
            s["green_s"]  = upd.get("green_s", s["green_s"])
            s["red_s"]    = s["green_s"] + 10
            s["adaptive"] = False
            results.append({"signal_id": sid, "status": "updated"})
        else:
            results.append({"signal_id": sid, "status": "not_found"})
    return {"results": results, "applied_at": datetime.now(timezone.utc).isoformat()}

@router.get("/{signal_id}")
async def get_signal(signal_id: str):
    s = store.signals.get(signal_id.upper())
    if not s:
        raise HTTPException(404, f"Signal {signal_id} not found")
    return s

@router.put("/{signal_id}")
async def update_signal(signal_id: str, body: SignalUpdateBody):
    s = store.signals.get(signal_id.upper())
    if not s:
        raise HTTPException(404, f"Signal {signal_id} not found")
    s["green_s"]    = body.green_s
    s["red_s"]      = body.green_s + 10
    s["adaptive"]   = False
    s["updated_at"] = datetime.now(timezone.utc).isoformat()
    store.add_alert("info", "SYSTEM", f"Manual override: {signal_id} green set to {body.green_s}s. Reason: {body.reason or 'operator command'}.")
    await store.broadcast({"type": "signal_update", "payload": s})
    return {"status": "updated", **s}

@router.post("/{signal_id}/reset")
async def reset_signal(signal_id: str):
    s = store.signals.get(signal_id.upper())
    if not s:
        raise HTTPException(404, f"Signal {signal_id} not found")
    s["adaptive"]   = True
    s["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"status": "adaptive_restored", "signal_id": signal_id}
