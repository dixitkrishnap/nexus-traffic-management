"""
scripts/demo_client.py

NEXUS Backend — Interactive Demo Client
────────────────────────────────────────
Demonstrates every backend capability in a clean terminal output.
Run: python scripts/demo_client.py

What it shows:
  1. Live system metrics
  2. All 12 zone statuses
  3. AI natural language chat (4 different queries)
  4. LLM congestion predictions
  5. Signal timing recommendations
  6. Route optimizer
  7. Emergency corridor activation + deactivation
  8. IoT sensor data ingestion
  9. Analytics summary
  10. WebSocket live stream (5 updates)
"""

import asyncio
import httpx
import json
import websockets
import sys
from datetime import datetime

BASE = "http://localhost:8000"
WS   = "ws://localhost:8000/api/traffic/ws"


# ── Console formatting ────────────────────────────────────

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"
LINE    = "─" * 60


def hdr(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{LINE}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{LINE}{RESET}")


def ok(label: str, value: str = "") -> None:
    print(f"  {GREEN}✔{RESET}  {BOLD}{label}{RESET}  {DIM}{value}{RESET}")


def info(label: str, value: str = "") -> None:
    print(f"  {CYAN}→{RESET}  {label}  {value}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}")


def err(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}")


def sep() -> None:
    print(f"  {DIM}{'·' * 54}{RESET}")


# ── HTTP helper ───────────────────────────────────────────

async def get(client: httpx.AsyncClient, path: str) -> dict:
    r = await client.get(f"{BASE}{path}")
    r.raise_for_status()
    return r.json()


async def post(client: httpx.AsyncClient, path: str, body: dict | None = None,
               params: dict | None = None) -> dict:
    r = await client.post(f"{BASE}{path}", json=body, params=params)
    r.raise_for_status()
    return r.json()


# ── Demo sections ─────────────────────────────────────────

async def demo_health(client):
    hdr("1 / 10  —  SYSTEM HEALTH CHECK")
    d = await get(client, "/health")
    ok("Status",   d["status"])
    ok("Version",  d["version"])
    ok("LLM Mode", d["llm"])
    sep()
    for svc, state in d["services"].items():
        info(f"{svc:<22}", state)
    m = d["metrics"]
    sep()
    ok("Vehicles tracked", f"{m['total_vehicles']:,}")
    ok("Flow efficiency",  f"{m['flow_efficiency']}%")
    ok("Avg delay",        f"{m['avg_delay_min']} min")
    ok("Active incidents", str(m["active_incidents"]))
    ok("Adaptive signals", f"{m['adaptive_signals']}/12")


async def demo_zones(client):
    hdr("2 / 10  —  LIVE ZONE STATUS (all 12 zones)")
    d = await get(client, "/api/traffic/zones")
    COLS = f"  {'ID':<5} {'Name':<26} {'Congestion':>10} {'Speed':>8} {'Wait':>6} {'Status':<10}"
    print(COLS)
    print(f"  {DIM}{'─'*56}{RESET}")
    for z in sorted(d["zones"], key=lambda x: -x["congestion"]):
        c   = z["congestion"]
        pct = f"{round(c*100)}%"
        col = RED if z["status"]=="critical" else YELLOW if z["status"]=="warning" else GREEN
        print(
            f"  {z['zone_id']:<5} {z['name']:<26} "
            f"{col}{pct:>10}{RESET} "
            f"{z['speed_ms']:>7.1f}m/s "
            f"{z['wait_time_s']:>5.0f}s  "
            f"{col}{z['status']:<10}{RESET}"
        )


async def demo_ai_chat(client):
    hdr("3 / 10  —  AI NATURAL LANGUAGE INTERFACE")
    queries = [
        "What is the current traffic status across the city?",
        "What is the fastest route to the airport right now?",
        "Explain how the AI and IoT system works in simple terms.",
        "Which signals need adjustment and why?",
    ]
    for q in queries:
        print(f"\n  {BOLD}Q: {q}{RESET}")
        d = await post(client, "/api/ai/chat", {"message": q})
        # Word-wrap reply at 70 chars
        words, line = d["reply"].split(), ""
        for w in words:
            if len(line) + len(w) > 70:
                print(f"    {DIM}{line}{RESET}")
                line = w
            else:
                line += (" " if line else "") + w
        if line:
            print(f"    {DIM}{line}{RESET}")
        print(f"    {CYAN}Intent: {d['intent']}  |  Confidence: {d.get('confidence',0):.0%}  |  {d['latency_ms']}ms{RESET}")
        if d["actions"]:
            for a in d["actions"]:
                print(f"    {GREEN}⚡ {a}{RESET}")


async def demo_predictions(client):
    hdr("4 / 10  —  LLM CONGESTION PREDICTIONS (60-min horizon)")
    d = await get(client, "/api/ai/predict")
    print(f"  {'Zone':<5} {'Name':<26} {'Now':>6} {'60min':>7} {'Conf':>6}  Recommendation")
    print(f"  {DIM}{'─'*78}{RESET}")
    for p in d["predictions"][:6]:
        now  = round(p["current_congestion"]  * 100)
        pred = round(p["predicted_congestion"] * 100)
        col  = RED if pred>=75 else YELLOW if pred>=55 else GREEN
        trend = "↑" if pred > now else "↓" if pred < now else "→"
        rec_short = p["recommendation"][:42] + "…" if len(p["recommendation"]) > 42 else p["recommendation"]
        print(
            f"  {p['zone_id']:<5} {p['zone_name']:<26} "
            f"{now:>5}%  {col}{pred:>5}% {trend}{RESET}  "
            f"{p['confidence']:.0%}   {DIM}{rec_short}{RESET}"
        )


async def demo_signals(client):
    hdr("5 / 10  —  ADAPTIVE SIGNAL CONTROL")
    # Show current state
    d = await get(client, "/api/signals/")
    print(f"  {'Signal':<12} {'Intersection':<30} {'Phase':<7} {'Green':>6} {'Mode':<8}")
    print(f"  {DIM}{'─'*62}{RESET}")
    for s in d["signals"]:
        col   = GREEN if s["phase"]=="G" else YELLOW if s["phase"]=="Y" else RED
        mode  = GREEN+"AUTO"+RESET if s["adaptive"] else YELLOW+"MANUAL"+RESET
        print(
            f"  {s['signal_id']:<12} {s['intersection']:<30} "
            f"{col}{s['phase']:<7}{RESET} {s['green_s']:>5}s  {mode}"
        )
    sep()
    # Apply a manual override
    r = await client.put(f"{BASE}/api/signals/SIG-A14", json={
        "green_s": 80,
        "reason":  "Demo: T.Nagar peak hour override"
    })
    r.raise_for_status()
    ok("Manual override applied", "SIG-A14 green → 80s")

    # Get LLM recommendations
    recs = await get(client, "/api/signals/optimize")
    sep()
    print(f"  {BOLD}LLM Signal Optimisation Recommendations:{RESET}")
    for r in recs["recommendations"][:4]:
        delta_str = (f"{GREEN}+{r['delta_s']}s{RESET}" if r["delta_s"] > 0
                     else f"{RED}{r['delta_s']}s{RESET}" if r["delta_s"] < 0
                     else f"{DIM}no change{RESET}")
        print(f"  {r['signal_id']:<12} {r['current_green_s']}s → {r['recommended_green_s']}s  ({delta_str})  {DIM}{r['reasoning'][:45]}…{RESET}")

    # Restore adaptive
    await client.post(f"{BASE}/api/signals/SIG-A14/reset")
    ok("SIG-A14 restored to adaptive LLM control")


async def demo_routes(client):
    hdr("6 / 10  —  ROUTE OPTIMIZER")
    d = await get(client, "/api/traffic/routes?origin=T.Nagar&destination=Airport")
    print(f"  Origin: {BOLD}{d['origin']}{RESET}  →  Destination: {BOLD}{d['destination']}{RESET}\n")
    for o in d["options"]:
        col   = GREEN if o["rank"]==1 else YELLOW if o["rank"]==2 else RED
        badge = o["status"]
        print(
            f"  {col}#{o['rank']}{RESET}  {BOLD}{o['name']:<22}{RESET}  "
            f"via {o['via']:<18}  "
            f"ETA: {col}{o['eta_min']:>2} min{RESET}  "
            f"{round(o['congestion']*100):>3}% load  "
            f"{col}[{badge}]{RESET}"
        )


async def demo_emergency(client):
    hdr("7 / 10  —  EMERGENCY CORRIDOR CONTROL")

    print(f"\n  {BOLD}Activating ambulance corridor…{RESET}")
    d = await post(client, "/api/emergency/activate", {
        "emergency_type": "ambulance",
        "origin":         "T.Nagar",
        "destination":    "Apollo Hospital",
        "notes":          "Cardiac emergency — demo",
    })
    ok("Incident ID",    d["incident_id"])
    ok("Type",           d["emergency_type"])
    ok("Status",         d["status"])
    ok("ETA",            f"{d['eta_min']} min")
    ok("Corridor",       ", ".join(d["corridor"]))
    ok("Message",        d["message"])

    sep()
    print(f"  {BOLD}Verifying corridor signals set to GREEN…{RESET}")
    for sid in d["corridor"]:
        r = await client.get(f"{BASE}/api/signals/{sid}")
        s = r.json()
        col = GREEN if s["phase"]=="G" else RED
        print(f"    {sid:<12}  phase={col}{s['phase']}{RESET}  green={s['green_s']}s  adaptive={s['adaptive']}")

    sep()
    await asyncio.sleep(1)
    print(f"  {BOLD}Clearing emergency…{RESET}")
    result = await post(client, "/api/emergency/deactivate")
    ok("Emergency cleared", result.get("status", "RESOLVED"))
    ok("Signals restored to adaptive control")


async def demo_iot_sensor(client):
    hdr("8 / 10  —  IoT SENSOR INGESTION")
    print(f"  Simulating readings from physical sensor nodes…\n")
    sensors = [
        ("SNS-Z1-01", "Z1", 280, 11.2, 68.0, 22.0, 2200.0, 65.5),
        ("SNS-Z4-01", "Z4", 120, 19.5, 22.0,  4.0,  950.0, 54.2),
        ("SNS-Z9-01", "Z9", 310,  8.1, 74.0, 28.0, 2650.0, 69.1),
    ]
    for sid, zid, veh, spd, occ, wt, co2, noise in sensors:
        r = await client.post(f"{BASE}/api/traffic/sensor", params={
            "sensor_id":     sid,
            "zone_id":       zid,
            "vehicle_count": veh,
            "avg_speed_ms":  spd,
            "occupancy_pct": occ,
            "wait_time_s":   wt,
            "co2_mgs":       co2,
            "noise_db":      noise,
        })
        r.raise_for_status()
        d = r.json()
        alert_msg = d["alert"]["message"][:45] + "…" if d.get("alert") else "no threshold crossing"
        ok(f"{sid} → {zid}", f"{veh}v  {spd}m/s  {occ}% occ  CO₂={co2}mg/s")
        if d.get("alert"):
            print(f"    {YELLOW}⚠ Alert triggered: {alert_msg}{RESET}")

    sep()
    print(f"  {BOLD}SUMO-style vehicle telemetry for Z9:{RESET}")
    t = await get(client, "/api/traffic/telemetry/Z9")
    rows = [
        ("lane",          t["lane_id"]),
        ("speed",         f"{t['speed_ms']} m/s"),
        ("wait time",     f"{t['wait_time_s']} s"),
        ("CO2",           f"{t['co2_mgs']} mg/s"),
        ("NOx",           f"{t['nox_mgs']} mg/s"),
        ("fuel",          f"{t['fuel_mls']} ml/s"),
        ("noise",         f"{t['noise_db']} dB"),
    ]
    for k, v in rows:
        print(f"    {k:<14} {v}")


async def demo_analytics(client):
    hdr("9 / 10  —  ANALYTICS & ENVIRONMENTAL IMPACT")

    d = await get(client, "/api/analytics/daily")
    ok("Date",            d["date"])
    ok("Total vehicles",  f"{d['total_vehicles']:,}")
    ok("Peak hour",       f"{d['peak_hour']:02d}:00")
    ok("Avg efficiency",  f"{d['avg_efficiency']}%")
    ok("Fuel saved",      f"{d['fuel_saved_l']} L")
    ok("CO₂ reduced",     f"{d['co2_reduced_kg']} kg")

    sep()
    env = await get(client, "/api/analytics/environment")
    ok("LLM decisions today", str(env["llm_decisions_today"]))
    ok("Noise reduction",     f"{env['noise_reduction_pct']}%")
    ok("Delay saved / trip",  f"{env['avg_delay_saved_min']} min")

    sep()
    print(f"  {BOLD}7-Day Efficiency Trend:{RESET}")
    trend = (await get(client, "/api/analytics/efficiency"))["trend"]
    for t in trend:
        bar_len = round(t["efficiency"] / 5)
        bar = "█" * bar_len
        col = GREEN if t["efficiency"]>75 else YELLOW if t["efficiency"]>60 else RED
        is_today = "← today" if t == trend[-1] else ""
        print(f"    {t['date']}  {col}{bar:<20}{RESET} {t['efficiency']:.1f}%  {DIM}{is_today}{RESET}")


async def demo_websocket():
    hdr("10 / 10  —  WEBSOCKET LIVE STREAM (5 updates)")
    print(f"  Connecting to {WS}…\n")
    try:
        async with websockets.connect(WS, open_timeout=5) as ws:
            ok("WebSocket connected")
            for i in range(5):
                raw  = await asyncio.wait_for(ws.recv(), timeout=35)
                data = json.loads(raw)
                msg_type = data.get("type", "unknown")
                if msg_type == "state_update":
                    m = data.get("metrics", {})
                    z_crit = sum(1 for z in data.get("zones",[]) if z.get("status")=="critical")
                    print(
                        f"  [{i+1}/5]  {CYAN}state_update{RESET}  "
                        f"vehicles={m.get('total_vehicles','?'):,}  "
                        f"eff={m.get('flow_efficiency','?')}%  "
                        f"incidents={m.get('active_incidents','?')}  "
                        f"critical_zones={z_crit}"
                    )
                elif msg_type == "ping":
                    print(f"  [{i+1}/5]  {DIM}ping  {data.get('ts','')}{RESET}")
                else:
                    print(f"  [{i+1}/5]  {YELLOW}{msg_type}{RESET}")
    except Exception as e:
        warn(f"WebSocket demo skipped ({e}). Start the server first.")


# ── Main ──────────────────────────────────────────────────

async def main():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  NEXUS Traffic Intelligence System — Backend Demo{RESET}")
    print(f"{BOLD}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")

    async with httpx.AsyncClient(timeout=30) as client:
        # Quick connectivity check
        try:
            r = await client.get(f"{BASE}/health")
            r.raise_for_status()
        except Exception as e:
            err(f"Cannot reach backend at {BASE}")
            err(f"Start the server: uvicorn main:app --reload")
            err(f"Error: {e}")
            sys.exit(1)

        await demo_health(client)
        await demo_zones(client)
        await demo_ai_chat(client)
        await demo_predictions(client)
        await demo_signals(client)
        await demo_routes(client)
        await demo_emergency(client)
        await demo_iot_sensor(client)
        await demo_analytics(client)

    await demo_websocket()

    print(f"\n{BOLD}{GREEN}{'═'*60}{RESET}")
    print(f"{BOLD}{GREEN}  Demo complete. All systems operational.{RESET}")
    print(f"{BOLD}{GREEN}  API docs → http://localhost:8000/docs{RESET}")
    print(f"{BOLD}{GREEN}{'═'*60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
