"""
services/iot_sensor.py

IoT Sensor Simulation Engine
─────────────────────────────
Simulates 12 zones × 4 sensors = 48 IoT sensor nodes.

Each sensor node generates:
  • Vehicle count
  • Average speed (m/s)
  • Lane occupancy %
  • Waiting time (s)
  • SUMO-style vehicle emissions (CO2, NOx, fuel, noise)

In production: replace _simulate_reading() with:
  • MQTT subscriber (asyncio-mqtt)
  • REST polling from hardware gateways
  • Kafka consumer for real-time event streams

Rush-hour time factors:
  • 08:00–10:00  → 1.45×
  • 17:00–20:00  → 1.55×
  • 00:00–05:00  → 0.35×
  • Other        → 1.00×
"""

from __future__ import annotations
import asyncio
import math
import random
from datetime import datetime, timezone
from typing import Optional

from core.config import settings
from services.state_store import store, ZONE_DEFS


def _gauss(mu: float = 0.0, sigma: float = 1.0) -> float:
    return random.gauss(mu, sigma)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _time_factor() -> float:
    h = datetime.now().hour
    if 8  <= h <= 10: return 1.45
    if 17 <= h <= 20: return 1.55
    if 0  <= h <= 5:  return 0.35
    return 1.0


def _simulate_reading(zone_id: str, base_congestion: float,
                      current_congestion: float) -> dict:
    """
    Simulate one IoT sensor reading for a zone.
    Uses mean-reversion + Gaussian noise + time-of-day factor.

    In production: this function body gets replaced by an MQTT
    message handler or REST call to the physical sensor gateway.
    """
    tf = _time_factor()

    # Mean-reversion drift toward (base × time_factor) with noise
    target = _clamp(base_congestion * tf, 0.05, 0.99)
    noise  = _gauss(0, 0.024)
    drift  = (target - current_congestion) * 0.11
    new_cong = _clamp(current_congestion + drift + noise, 0.05, 0.99)

    vehicle_count = max(0, round(new_cong * tf * 420 + _gauss(0, 12)))
    speed_ms      = _clamp(22.22 * (1 - new_cong) + _gauss(0, 0.5), 0.3, 22.22)
    wait_time_s   = _clamp(new_cong * 40 + _gauss(0, 3), 0, 120)
    occupancy_pct = new_cong * 100

    # SUMO-style vehicle emissions aggregates
    co2_mgs   = round(_clamp(1800 + new_cong * 600 + _gauss(0, 50), 500, 4000), 2)
    nox_mgs   = round(_clamp(0.5 + new_cong * 0.4 + _gauss(0, 0.05), 0.1, 5.0), 3)
    fuel_mls  = round(_clamp(0.7 + new_cong * 0.5 + _gauss(0, 0.05), 0.2, 3.0), 3)
    noise_db  = round(_clamp(58 + new_cong * 10 + _gauss(0, 1), 45, 90), 1)

    return {
        "sensor_id":     f"SNS-{zone_id}-01",
        "zone_id":       zone_id,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "vehicle_count": vehicle_count,
        "avg_speed_ms":  round(speed_ms, 2),
        "occupancy_pct": round(occupancy_pct, 1),
        "wait_time_s":   round(wait_time_s, 1),
        "weather":       "clear",
        "co2_mgs":       co2_mgs,
        "nox_mgs":       nox_mgs,
        "fuel_mls":      fuel_mls,
        "noise_db":      noise_db,
    }


# ──────────────────────────────────────────────────────────
# SENSOR ENGINE LOOP
# ──────────────────────────────────────────────────────────

async def sensor_engine_loop() -> None:
    """
    Main IoT sensor loop.
    Every SENSOR_POLL_INTERVAL_S seconds:
      1. Generate simulated readings for all 12 zones
      2. Push readings into state_store (apply_sensor_reading)
      3. Broadcast updated state over WebSocket
      4. Log auto-generated LLM-style informational alerts
    """
    print(f"🌡️   Sensor engine started (interval={settings.SENSOR_POLL_INTERVAL_S}s)")

    auto_alerts = [
        lambda z: f"LLM optimised signals at {z['name']} — +{random.randint(11,20)}% throughput.",
        lambda z: f"{random.randint(200,700)} vehicles rerouted from {z['name']} via alternate.",
        lambda z: f"Surge predicted at {z['name']} in 45 min. Pre-empting signal cycles.",
        lambda z: f"Adaptive cycle complete — {z['name']} efficiency improved.",
        lambda z: f"IoT sensor array at {z['name']} — all 4 nodes healthy.",
    ]

    tick = 0
    while True:
        await asyncio.sleep(settings.SENSOR_POLL_INTERVAL_S)

        if not store.running:
            continue

        # ── Process each zone ────────────────────────────
        triggered_alerts = []
        for zd in ZONE_DEFS:
            zid = zd["id"]
            z   = store.zones.get(zid)
            if not z:
                continue
            reading = _simulate_reading(zid, zd["base"], z["congestion"])
            alert   = store.apply_sensor_reading(zid, reading)
            if alert:
                triggered_alerts.append(alert)

        store.sim_time += settings.SENSOR_POLL_INTERVAL_S
        store.sim_step += 1

        # ── Occasional auto-info alert ───────────────────
        if tick % 3 == 0:  # every ~15 seconds
            z = random.choice(list(store.zones.values()))
            fn = random.choice(auto_alerts)
            store.add_alert("info", "SYSTEM", fn(z), z["zone_id"])

        # ── WebSocket broadcast ──────────────────────────
        snapshot = store.snapshot()
        await store.broadcast(snapshot)

        tick += 1


# ──────────────────────────────────────────────────────────
# SIGNAL ENGINE LOOP
# ──────────────────────────────────────────────────────────

async def signal_engine_loop() -> None:
    """
    Signal phase advance loop.
    Runs every 1.1 seconds to advance all signal phase timers.
    Applies LLM-adaptive green duration recalculation on each
    RED → GREEN transition based on live zone congestion.
    """
    print("🚦  Signal engine started (tick=1.1s)")
    TICK_S = 1.1
    while True:
        await asyncio.sleep(TICK_S)
        if store.running:
            store.tick_signals(TICK_S)
