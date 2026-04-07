"""
api/routes/alerts.py

Alert Feed API
──────────────
GET  /api/alerts/              Paginated alert feed
GET  /api/alerts/stats         Alert statistics
POST /api/alerts/              Create manual alert
PUT  /api/alerts/{id}/resolve  Resolve an alert
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.state_store import store

router = APIRouter()


class AlertCreateBody(BaseModel):
    level:      str
    alert_type: str
    message:    str
    zone_id:    Optional[str] = None


@router.get("/")
async def list_alerts(
    limit:    int  = Query(20, le=100),
    offset:   int  = Query(0),
    level:    str  = Query(None),
    resolved: bool = Query(None),
):
    alerts = store.alerts
    if level:
        alerts = [a for a in alerts if a["level"] == level]
    if resolved is not None:
        alerts = [a for a in alerts if a["resolved"] == resolved]
    unresolved = sum(1 for a in store.alerts if not a["resolved"])
    return {
        "alerts":     alerts[offset: offset + limit],
        "total":      len(alerts),
        "unresolved": unresolved,
    }


@router.get("/stats")
async def alert_stats():
    counts = {}
    types  = {}
    for a in store.alerts:
        counts[a["level"]] = counts.get(a["level"], 0) + 1
        types[a["alert_type"]] = types.get(a["alert_type"], 0) + 1
    return {
        "by_level":   counts,
        "by_type":    types,
        "total":      len(store.alerts),
        "unresolved": sum(1 for a in store.alerts if not a["resolved"]),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


@router.post("/")
async def create_alert(body: AlertCreateBody):
    alert = store.add_alert(body.level, body.alert_type, body.message, body.zone_id)
    return {"status": "created", "alert": alert}


@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    for a in store.alerts:
        if a["alert_id"] == alert_id.upper():
            a["resolved"]    = True
            a["resolved_at"] = datetime.now(timezone.utc).isoformat()
            return {"status": "resolved", "alert_id": alert_id}
    raise HTTPException(404, f"Alert {alert_id} not found")
