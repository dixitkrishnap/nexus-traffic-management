"""
api/routes/traffic.py

Traffic & Zone API
──────────────────
GET  /api/traffic/zones              All zone snapshots
GET  /api/traffic/zones/{zone_id}    Single zone
GET  /api/traffic/metrics            System-wide KPIs
GET  /api/traffic/routes             Route optimizer
POST /api/traffic/sensor             IoT sensor ingestion (hardware gateway)
GET  /api/traffic/telemetry/{zone}   SUMO-style vehicle telemetry
WS   /api/traffic/ws                 WebSocket live feed
"""

from __future__ import annotations
import asyncio
import random
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query

from services.state_store import store
from services.iot_sensor import _simulate_reading

router = APIRouter()


# ── Zones ─────────────────────────────────────────────────

@router.get("/zones")
async def list_zones(status: str = Query(None, description="Filter: normal|warning|critical")):
    zones = list(store.zones.values())
    if status:
        zones = [z for z in zones if z["status"] == status]
    return {
        "zones":     zones,
        "total":     len(zones),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/zones/{zone_id}")
async def get_zone(zone_id: str):
    z = store.zones.get(zone_id.upper())
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    return z


# ── Metrics ───────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics():
    return store.get_metrics()


# ── Routes ────────────────────────────────────────────────

@router.get("/routes")
async def get_routes(
    origin:      str = Query("Current Location"),
    destination: str = Query("Airport"),
):
    return store.compute_routes(origin, destination)


# ── IoT Sensor Ingestion ──────────────────────────────────

@router.post("/sensor")
async def ingest_sensor(
    sensor_id:     str,
    zone_id:       str,
    vehicle_count: int,
    avg_speed_ms:  float,
    occupancy_pct: float,
    wait_time_s:   float = 0.0,
    co2_mgs:       float = 0.0,
    nox_mgs:       float = 0.0,
    fuel_mls:      float = 0.0,
    noise_db:      float = 0.0,
    weather:       str   = "clear",
):
    """
    IoT gateway ingestion endpoint.

    In production: your physical sensor gateway (Raspberry Pi,
    Arduino, commercial traffic sensor) POSTs here. The backend
    merges the reading into live state and updates WebSocket clients.

    For the demo: the sensor simulator calls apply_sensor_reading
    directly. This endpoint is for external hardware integration.
    """
    zone_id = zone_id.upper()
    if zone_id not in store.zones:
        raise HTTPException(400, f"Unknown zone: {zone_id}")

    reading = {
        "vehicle_count": vehicle_count,
        "avg_speed_ms":  avg_speed_ms,
        "occupancy_pct": occupancy_pct,
        "wait_time_s":   wait_time_s,
        "co2_mgs":       co2_mgs,
        "nox_mgs":       nox_mgs,
        "fuel_mls":      fuel_mls,
        "noise_db":      noise_db,
    }
    alert = store.apply_sensor_reading(zone_id, reading)

    # Broadcast update
    await store.broadcast({
        "type": "zone_update",
        "payload": store.zones[zone_id],
    })

    return {
        "status":    "accepted",
        "zone_id":   zone_id,
        "sensor_id": sensor_id,
        "alert":     alert,
    }


# ── Vehicle Telemetry (SUMO-style) ────────────────────────

@router.get("/telemetry/{zone_id}")
async def get_telemetry(zone_id: str):
    """
    Returns SUMO-style per-vehicle telemetry for the worst vehicle
    in the specified zone (Image 2 data — speed, CO2, NOx, fuel, etc.)
    """
    zone_id = zone_id.upper()
    z = store.zones.get(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")

    c = z["congestion"]
    spd = z["speed_ms"]

    return {
        "vehicle_id":   f"vehicle:{random.randint(0,200)}",
        "lane_id":      f"gneE{random.randint(0,5)}_{random.randint(0,3)}",
        "position_m":   round(80 + random.uniform(0, 140), 2),
        "speed_ms":     round(spd + random.gauss(0, 0.3), 2),
        "lat_offset_m": 0.0,
        "accel_ms2":    round(random.gauss(0, 0.15), 2),
        "angle_deg":    round(90 + random.uniform(-5, 5), 2),
        "slope_deg":    0.0,
        "speed_factor": 1.0,
        "wait_time_s":  round(z["wait_time_s"] + random.gauss(0, 1), 2),
        "time_loss_s":  round(z["wait_time_s"] * 0.6, 2),
        "impatience":   round(c * 0.8, 2),
        "co2_mgs":      z["co2_mgs"],
        "co_mgs":       round(0.2 + c * 0.1, 3),
        "hc_mgs":       round(0.04 + c * 0.02, 3),
        "nox_mgs":      z["nox_mgs"],
        "pmx_mgs":      round(0.008 + c * 0.008, 4),
        "fuel_mls":     z["fuel_mls"],
        "electricity_whs": 0.0,
        "noise_db":     z["noise_db"],
        "lc_state_r":   "unknown",
        "lc_state_l":   "unknown",
        "zone_id":      zone_id,
        "zone_name":    z["name"],
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }


# ── Simulation Control ────────────────────────────────────

@router.post("/sim/run")
async def sim_run():
    store.running = True
    return {"status": "running"}

@router.post("/sim/pause")
async def sim_pause():
    store.running = not store.running
    return {"status": "running" if store.running else "paused"}

@router.post("/sim/reset")
async def sim_reset():
    store.running = False
    store.sim_time = 0
    store.sim_step = 0
    return {"status": "reset"}

@router.get("/sim/status")
async def sim_status():
    return {
        "running":  store.running,
        "sim_time": store.sim_time,
        "sim_step": store.sim_step,
    }


# ── WebSocket ─────────────────────────────────────────────

@router.websocket("/ws")
async def traffic_ws(websocket: WebSocket):
    """
    Live WebSocket feed.
    Pushes full state updates every SENSOR_POLL_INTERVAL_S seconds.
    Clients receive: zones, signals, metrics, alerts, emergency status.

    Connect: ws://localhost:8000/api/traffic/ws
    """
    await websocket.accept()
    q = store.subscribe()
    try:
        # Send immediate snapshot on connect
        await websocket.send_json(store.snapshot())

        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                await websocket.send_json(msg)
            except asyncio.TimeoutError:
                # Heartbeat to keep connection alive
                await websocket.send_json({
                    "type": "ping",
                    "ts":   datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        pass
    finally:
        store.unsubscribe(q)
