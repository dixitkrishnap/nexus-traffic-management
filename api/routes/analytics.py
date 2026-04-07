"""
api/routes/analytics.py

Analytics API
─────────────
GET /api/analytics/daily         Today's aggregated stats
GET /api/analytics/hourly        Hourly volume curve
GET /api/analytics/heatmap       Zone congestion heatmap data
GET /api/analytics/efficiency    N-day efficiency trend
GET /api/analytics/signals/perf  Per-signal throughput stats
GET /api/analytics/environment   Environmental impact summary
"""

from __future__ import annotations
import random
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Query

from services.state_store import store

router = APIRouter()


def _hourly_profile():
    """Chennai traffic curve — realistic 24-hour shape."""
    base = [
        120,  80,  60,  55,  70, 140,
        320, 580, 720, 640, 510, 480,
        520, 540, 580, 610, 720, 850,
        780, 620, 480, 360, 260, 180,
    ]
    now_h = datetime.now().hour
    return [
        {
            "hour":       h,
            "vehicles":   base[h] * 4 + random.randint(-30, 30),
            "avg_speed":  round(max(5, 55 - (base[h] / 850) * 45), 1),
            "incidents":  random.randint(0, 3) if base[h] > 500 else 0,
            "is_current": h == now_h,
        }
        for h in range(24)
    ]


@router.get("/daily")
async def daily_summary():
    hourly  = _hourly_profile()
    total   = sum(h["vehicles"] for h in hourly)
    peak_h  = max(hourly, key=lambda h: h["vehicles"])
    m       = store.get_metrics()
    fuel_saved  = round(total * 0.018, 1)
    co2_reduced = round(fuel_saved * 2.31, 1)
    return {
        "date":             datetime.now().strftime("%Y-%m-%d"),
        "total_vehicles":   total,
        "peak_hour":        peak_h["hour"],
        "peak_volume":      peak_h["vehicles"],
        "avg_efficiency":   m["flow_efficiency"],
        "total_incidents":  m["active_incidents"] + random.randint(2, 8),
        "fuel_saved_l":     fuel_saved,
        "co2_reduced_kg":   co2_reduced,
        "hourly":           hourly,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
    }


@router.get("/hourly")
async def hourly_volume():
    return {"hourly": _hourly_profile()}


@router.get("/heatmap")
async def congestion_heatmap():
    return {
        "zones": [
            {
                "zone_id":    zid,
                "name":       z["name"],
                "lat":        z["lat"],
                "lng":        z["lng"],
                "congestion": round(z["congestion"], 3),
                "congestion_pct": round(z["congestion"] * 100),
                "vehicles":   z["vehicles"],
                "speed_ms":   z["speed_ms"],
                "status":     z["status"],
            }
            for zid, z in store.zones.items()
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/efficiency")
async def efficiency_trend(days: int = Query(7, le=30)):
    today = datetime.now()
    trend = []
    for d in range(days - 1, -1, -1):
        date    = today - timedelta(days=d)
        base_eff = 68 + (days - d) * 0.4 + random.gauss(0, 1.5)
        trend.append({
            "date":       date.strftime("%Y-%m-%d"),
            "efficiency": round(min(95, max(55, base_eff)), 1),
            "incidents":  random.randint(2, 10),
            "vehicles":   random.randint(28000, 36000),
        })
    return {
        "trend":          trend,
        "days":           days,
        "avg_efficiency": round(sum(t["efficiency"] for t in trend) / len(trend), 1),
    }


@router.get("/signals/perf")
async def signal_performance():
    perf = []
    for sid, s in store.signals.items():
        z   = store.zones.get(s["zone_id"], {})
        c   = z.get("congestion", 0.5)
        cyc = s["green_s"] + s["yellow_s"] + s["red_s"]
        green_pct  = round(s["green_s"] / cyc * 100, 1)
        throughput = round((1 - c) * green_pct * 3.5)
        perf.append({
            "signal_id":        sid,
            "intersection":     s["intersection"],
            "zone_id":          s["zone_id"],
            "adaptive":         s["adaptive"],
            "phase":            s["phase"],
            "green_s":          s["green_s"],
            "green_pct":        green_pct,
            "cycle_count":      s["cycle_count"],
            "throughput_vph":   throughput,
            "zone_congestion":  round(c, 3),
        })
    return {
        "signals":   perf,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/environment")
async def environmental_impact():
    m = store.get_metrics()
    v = m["total_vehicles"]
    return {
        "vehicles_tracked":   v,
        "fuel_saved_l_day":   round(v * 0.018, 1),
        "co2_reduced_kg_day": round(v * 0.042, 1),
        "nox_reduced_mg":     round(v * 0.12, 1),
        "noise_reduction_pct": round(m["flow_efficiency"] * 0.15, 1),
        "llm_decisions_today": store.sim_step * 12,
        "avg_delay_saved_min": round(max(0, 5 - m["avg_delay_min"]), 2),
        "timestamp":           datetime.now(timezone.utc).isoformat(),
    }
