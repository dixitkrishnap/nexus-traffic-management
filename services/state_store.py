"""
services/state_store.py

Central in-memory state store for live traffic data.
Holds current zone congestion, signal phases, alerts, emergency status.

In production: replace with Redis for multi-process/multi-node deployment.
All WebSocket subscribers receive state updates via asyncio.Queue fan-out.
"""

from __future__ import annotations
import asyncio
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.config import settings


# ──────────────────────────────────────────────────────────
# ZONE DEFINITIONS  (seed data — also in DB)
# ──────────────────────────────────────────────────────────

ZONE_DEFS = [
    {"id": "Z1",  "name": "Anna Salai Corridor",   "base": 0.55, "lat": 13.0674, "lng": 80.2376},
    {"id": "Z2",  "name": "OMR Tech Park",          "base": 0.40, "lat": 12.9120, "lng": 80.2284},
    {"id": "Z3",  "name": "T.Nagar Market Hub",     "base": 0.75, "lat": 13.0418, "lng": 80.2341},
    {"id": "Z4",  "name": "Airport Expressway",     "base": 0.25, "lat": 12.9900, "lng": 80.1637},
    {"id": "Z5",  "name": "Tambaram Junction",      "base": 0.60, "lat": 12.9249, "lng": 80.1000},
    {"id": "Z6",  "name": "Adyar Bridge",           "base": 0.35, "lat": 13.0012, "lng": 80.2565},
    {"id": "Z7",  "name": "Guindy Industrial",      "base": 0.50, "lat": 13.0067, "lng": 80.2206},
    {"id": "Z8",  "name": "Velachery Roundabout",   "base": 0.65, "lat": 12.9750, "lng": 80.2209},
    {"id": "Z9",  "name": "Koyambedu Terminus",     "base": 0.70, "lat": 13.0694, "lng": 80.1948},
    {"id": "Z10", "name": "Porur Junction",         "base": 0.45, "lat": 13.0337, "lng": 80.1567},
    {"id": "Z11", "name": "Sholinganallur Signal",  "base": 0.55, "lat": 12.8996, "lng": 80.2271},
    {"id": "Z12", "name": "Chromepet Crossroads",   "base": 0.30, "lat": 12.9516, "lng": 80.1462},
]

SIGNAL_DEFS = [
    {"id": "SIG-A01", "name": "Anna Salai / Mount Rd",     "zone": "Z1",  "green": 45},
    {"id": "SIG-A02", "name": "Anna Salai / Nandanam",     "zone": "Z1",  "green": 40},
    {"id": "SIG-A14", "name": "T.Nagar / Panagal Park",    "zone": "Z3",  "green": 35},
    {"id": "SIG-B07", "name": "OMR / Perungudi Jn",        "zone": "Z2",  "green": 50},
    {"id": "SIG-B12", "name": "OMR / Sholinganallur",      "zone": "Z11", "green": 45},
    {"id": "SIG-C22", "name": "Adyar / LB Road",           "zone": "Z6",  "green": 40},
    {"id": "SIG-C05", "name": "Airport / Meenambakkam",    "zone": "Z4",  "green": 55},
    {"id": "SIG-D03", "name": "Koyambedu / NH-48",         "zone": "Z9",  "green": 35},
    {"id": "SIG-D11", "name": "Guindy / Sardar Patel Rd",  "zone": "Z7",  "green": 45},
    {"id": "SIG-E08", "name": "Velachery / 100 Ft Rd",     "zone": "Z8",  "green": 40},
    {"id": "SIG-E14", "name": "Tambaram / GST Rd",         "zone": "Z5",  "green": 50},
    {"id": "SIG-F02", "name": "Porur / Arcot Rd",          "zone": "Z10", "green": 45},
]


def _gauss(mu: float = 0, sigma: float = 1) -> float:
    return random.gauss(mu, sigma)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status(c: float) -> str:
    if c >= settings.CONGESTION_CRIT_THRESHOLD:
        return "critical"
    if c >= settings.CONGESTION_WARN_THRESHOLD:
        return "warning"
    return "normal"


# ──────────────────────────────────────────────────────────
# STATE STORE
# ──────────────────────────────────────────────────────────

class TrafficStateStore:
    """
    Single source of truth for live traffic state.
    All services read/write through this object.
    """

    def __init__(self) -> None:
        self.zones:     Dict[str, dict] = {}
        self.signals:   Dict[str, dict] = {}
        self.alerts:    List[dict]      = []
        self.emergency: Optional[dict]  = None
        self.sim_time:  float           = 0.0
        self.sim_step:  int             = 0
        self.running:   bool            = True

        # WebSocket fan-out queues
        self._ws_queues: List[asyncio.Queue] = []

        self._init_zones()
        self._init_signals()

    # ── Initialisation ────────────────────────────────────

    def _init_zones(self) -> None:
        for d in ZONE_DEFS:
            c = d["base"]
            self.zones[d["id"]] = {
                "zone_id":       d["id"],
                "name":          d["name"],
                "lat":           d["lat"],
                "lng":           d["lng"],
                "base":          c,
                "congestion":    c,
                "vehicles":      int(c * 400 + random.randint(50, 150)),
                "speed_ms":      round(max(1.0, 22.22 * (1 - c)), 2),
                "wait_time_s":   round(c * 35, 1),
                "status":        _status(c),
                "incident_count": 0,
                # Vehicle telemetry (SUMO-style aggregates)
                "co2_mgs":       round(1800 + c * 600, 2),
                "nox_mgs":       round(0.5 + c * 0.4, 2),
                "fuel_mls":      round(0.7 + c * 0.5, 2),
                "noise_db":      round(58 + c * 10, 1),
                "updated_at":    _now(),
            }

    def _init_signals(self) -> None:
        phases = ["G", "Y", "R"]
        for d in SIGNAL_DEFS:
            ph = random.choice(phases)
            g  = d["green"]
            self.signals[d["id"]] = {
                "signal_id":    d["id"],
                "intersection": d["name"],
                "zone_id":      d["zone"],
                "phase":        ph,
                "elapsed_s":    random.uniform(0, g),
                "green_s":      g,
                "yellow_s":     settings.SIGNAL_YELLOW_S,
                "red_s":        g + 10,
                "adaptive":     True,
                "cycle_count":  0,
                "updated_at":   _now(),
            }

    # ── Zone tick (called by sensor engine) ──────────────

    _prev_statuses: Dict[str, str] = {}

    def apply_sensor_reading(self, zone_id: str, reading: dict) -> Optional[dict]:
        """
        Merge an IoT sensor reading into zone state.
        Returns an alert dict if threshold crossed, else None.
        """
        z = self.zones.get(zone_id)
        if not z:
            return None

        z["congestion"]  = _clamp(reading.get("occupancy_pct", z["congestion"] * 100) / 100, 0.05, 0.99)
        z["vehicles"]    = reading.get("vehicle_count", z["vehicles"])
        z["speed_ms"]    = round(reading.get("avg_speed_ms", z["speed_ms"]), 2)
        z["wait_time_s"] = round(reading.get("wait_time_s",  z["wait_time_s"]), 1)
        z["co2_mgs"]     = round(reading.get("co2_mgs",      z["co2_mgs"]), 2)
        z["nox_mgs"]     = round(reading.get("nox_mgs",      z["nox_mgs"]), 2)
        z["fuel_mls"]    = round(reading.get("fuel_mls",     z["fuel_mls"]), 2)
        z["noise_db"]    = round(reading.get("noise_db",     z["noise_db"]), 1)

        prev   = self._prev_statuses.get(zone_id, "normal")
        z["status"]     = _status(z["congestion"])
        z["updated_at"] = _now()
        self._prev_statuses[zone_id] = z["status"]

        alert = None
        if z["status"] != prev:
            if z["status"] == "critical":
                z["incident_count"] += 1
                alert = self._make_alert("critical", "CONGESTION",
                    f"Severe congestion — {z['name']}. LLM diversion active.", zone_id)
            elif z["status"] == "warning" and prev == "normal":
                alert = self._make_alert("warning", "CONGESTION",
                    f"Traffic building — {z['name']}. Signals adjusted.", zone_id)
            elif z["status"] == "normal" and prev != "normal":
                z["incident_count"] = max(0, z["incident_count"] - 1)
                alert = self._make_alert("success", "ROUTE_OPTIMIZED",
                    f"Flow restored — {z['name']}.", zone_id)

        if alert:
            self.alerts.insert(0, alert)
            self.alerts = self.alerts[:200]

        return alert

    # ── Signal tick (called by signal engine) ────────────

    def tick_signals(self, dt_s: float) -> None:
        for s in self.signals.values():
            s["elapsed_s"] += dt_s
            dur = s["green_s"] if s["phase"] == "G" else \
                  s["yellow_s"] if s["phase"] == "Y" else s["red_s"]

            if s["elapsed_s"] >= dur:
                s["elapsed_s"] = 0.0
                if s["phase"] == "G":
                    s["phase"] = "Y"
                elif s["phase"] == "Y":
                    s["phase"] = "R"
                else:
                    s["phase"] = "G"
                    s["cycle_count"] += 1
                    # Adaptive: recalculate green on new cycle start
                    if s["adaptive"]:
                        z = self.zones.get(s["zone_id"])
                        if z:
                            c = z["congestion"]
                            s["green_s"] = round(
                                settings.SIGNAL_MIN_GREEN_S +
                                c * (settings.SIGNAL_MAX_GREEN_S - settings.SIGNAL_MIN_GREEN_S)
                            )
                            s["red_s"] = s["green_s"] + 10
                s["updated_at"] = _now()

    # ── Metrics ──────────────────────────────────────────

    def get_metrics(self) -> dict:
        zs  = list(self.zones.values())
        veh = sum(z["vehicles"] for z in zs)
        avg_c = sum(z["congestion"] for z in zs) / len(zs)
        eff = round(100 - avg_c * 100, 1)
        delay = round(max(0.5, (100 - eff) / 10), 2)
        inc = sum(1 for z in zs if z["status"] == "critical")
        adp = sum(1 for s in self.signals.values() if s["adaptive"])
        return {
            "total_vehicles":   veh,
            "flow_efficiency":  eff,
            "avg_delay_min":    delay,
            "active_incidents": inc,
            "adaptive_signals": adp,
            "timestamp":        _now(),
        }

    def compute_routes(self, origin: str = "Current Location",
                       destination: str = "Airport") -> dict:
        route_defs = [
            {"name": "Via GST Road",      "via": "GST Expressway",    "dist": 12.4, "zones": ["Z4","Z5"]},
            {"name": "Via OMR Flyover",   "via": "OMR + Perungudi",   "dist": 14.1, "zones": ["Z2","Z11"]},
            {"name": "Via Anna Salai",    "via": "Anna Salai Direct",  "dist": 10.8, "zones": ["Z1","Z3"]},
            {"name": "Via Inner Ring Rd", "via": "IRR + Guindy",       "dist": 13.5, "zones": ["Z7","Z8"]},
        ]
        options = []
        for r in route_defs:
            c = sum(self.zones.get(z, {}).get("congestion", 0.5) for z in r["zones"]) / len(r["zones"])
            eta = round(r["dist"] / max(5, 40 * (1 - c)) * 60)
            options.append({**r, "congestion": round(c, 3), "eta_min": eta})

        options.sort(key=lambda x: x["eta_min"])
        statuses = ["OPTIMAL", "ALTERNATE", "ALTERNATE", "AVOID"]
        return {
            "origin":      origin,
            "destination": destination,
            "options": [{**o, "rank": i + 1, "status": statuses[min(i, 3)]}
                        for i, o in enumerate(options)],
            "computed_at": _now(),
        }

    # ── Alerts ───────────────────────────────────────────

    def _make_alert(self, level: str, alert_type: str,
                    message: str, zone_id: str | None = None) -> dict:
        return {
            "alert_id":   str(uuid.uuid4())[:8].upper(),
            "level":      level,
            "alert_type": alert_type,
            "message":    message,
            "zone_id":    zone_id,
            "timestamp":  _now(),
            "resolved":   False,
        }

    def add_alert(self, level: str, alert_type: str,
                  message: str, zone_id: str | None = None) -> dict:
        a = self._make_alert(level, alert_type, message, zone_id)
        self.alerts.insert(0, a)
        self.alerts = self.alerts[:200]
        return a

    # ── Emergency ────────────────────────────────────────

    EMG_CORRIDORS = {
        "ambulance": ["SIG-A01", "SIG-A02", "SIG-C22", "SIG-C05"],
        "fire":      ["SIG-D03", "SIG-D11", "SIG-A14"],
        "vip":       ["SIG-B07", "SIG-B12", "SIG-E08", "SIG-F02"],
    }
    EMG_MESSAGES = {
        "ambulance": "🚑 Ambulance corridor ACTIVE — Green wave Route 7B. ETA: 8 min.",
        "fire":      "🚒 Fire engine priority ACTIVE — Eastern corridor cleared.",
        "vip":       "⭐ VIP escort ACTIVE — All signals synchronized along route.",
        "lockdown":  "🔒 ZONE LOCKDOWN — All 12 signals set to RED HOLD.",
        "clear":     "✅ Emergency cleared — all signals restored to adaptive control.",
    }

    def activate_emergency(self, etype: str, origin=None, dest=None,
                           vehicle_id=None, notes=None) -> dict:
        corridor = list(self.signals.keys()) if etype == "lockdown" \
                   else self.EMG_CORRIDORS.get(etype, [])
        eta = 8 if etype == "ambulance" else 12

        for sid in corridor:
            s = self.signals.get(sid)
            if not s:
                continue
            s["adaptive"] = False
            if etype == "lockdown":
                s["phase"] = "R"; s["elapsed_s"] = 0; s["red_s"] = 9999
            else:
                s["phase"] = "G"; s["elapsed_s"] = 0; s["green_s"] = 120

        incident = {
            "incident_id":    str(uuid.uuid4())[:8].upper(),
            "emergency_type": etype,
            "origin":         origin,
            "destination":    dest,
            "vehicle_id":     vehicle_id,
            "status":         "ACTIVE",
            "corridor":       corridor,
            "eta_min":        eta,
            "notes":          notes,
            "message":        self.EMG_MESSAGES.get(etype, "Emergency protocol activated."),
            "activated_at":   _now(),
        }
        self.emergency = incident
        self.add_alert("critical", "EMERGENCY", incident["message"])
        return incident

    def clear_emergency(self) -> dict:
        if not self.emergency:
            return {"status": "no_active_emergency"}
        for sid in self.emergency.get("corridor", []):
            s = self.signals.get(sid)
            if s:
                s["adaptive"] = True
                s["phase"]    = "G"
                s["elapsed_s"] = 0
        prev = self.emergency
        self.emergency = None
        self.add_alert("success", "EMERGENCY",
                       "Emergency cleared — adaptive control restored to all signals.")
        return {**prev, "status": "RESOLVED", "resolved_at": _now()}

    # ── WebSocket pub/sub ─────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=80)
        self._ws_queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._ws_queues.remove(q)
        except ValueError:
            pass

    async def broadcast(self, msg: dict) -> None:
        dead = []
        for q in self._ws_queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    def snapshot(self) -> dict:
        """Full state snapshot for WebSocket initial push."""
        return {
            "type":      "state_update",
            "metrics":   self.get_metrics(),
            "zones":     list(self.zones.values()),
            "signals":   list(self.signals.values()),
            "alerts":    self.alerts[:20],
            "emergency": self.emergency,
            "sim_time":  self.sim_time,
            "sim_step":  self.sim_step,
            "running":   self.running,
        }


# Singleton — imported everywhere
store = TrafficStateStore()
