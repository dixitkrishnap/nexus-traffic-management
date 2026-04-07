"""
tests/test_api.py

Async test suite for NEXUS backend.
Run: pytest tests/ -v --asyncio-mode=auto

Tests cover every API endpoint + edge cases.
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client():
    from httpx import AsyncClient, ASGITransport
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


# ══════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════

class TestHealth:
    async def test_root_returns_html(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "NEXUS" in r.text

    async def test_health_check(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "healthy"
        assert "version" in d
        assert "services" in d
        assert d["services"]["sensor_engine"] == "running"
        assert d["services"]["signal_engine"] == "running"

    async def test_health_has_metrics(self, client):
        r = await client.get("/health")
        m = r.json()["metrics"]
        assert "total_vehicles" in m
        assert "flow_efficiency" in m
        assert 0 <= m["flow_efficiency"] <= 100


# ══════════════════════════════════════════════════════════
# TRAFFIC / ZONES
# ══════════════════════════════════════════════════════════

class TestTrafficZones:
    async def test_list_all_zones(self, client):
        r = await client.get("/api/traffic/zones")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 12
        assert len(d["zones"]) == 12

    async def test_zone_fields_present(self, client):
        r = await client.get("/api/traffic/zones")
        z = r.json()["zones"][0]
        for field in ["zone_id", "name", "congestion", "vehicles",
                      "speed_ms", "wait_time_s", "status"]:
            assert field in z, f"Missing field: {field}"

    async def test_congestion_in_range(self, client):
        r = await client.get("/api/traffic/zones")
        for z in r.json()["zones"]:
            assert 0 <= z["congestion"] <= 1, f"Bad congestion: {z['congestion']}"

    async def test_status_valid_enum(self, client):
        r = await client.get("/api/traffic/zones")
        valid = {"normal", "warning", "critical"}
        for z in r.json()["zones"]:
            assert z["status"] in valid, f"Bad status: {z['status']}"

    async def test_filter_by_status_normal(self, client):
        r = await client.get("/api/traffic/zones?status=normal")
        assert r.status_code == 200
        for z in r.json()["zones"]:
            assert z["status"] == "normal"

    async def test_filter_by_status_critical(self, client):
        r = await client.get("/api/traffic/zones?status=critical")
        assert r.status_code == 200

    async def test_get_single_zone_z1(self, client):
        r = await client.get("/api/traffic/zones/Z1")
        assert r.status_code == 200
        d = r.json()
        assert d["zone_id"] == "Z1"
        assert d["name"] == "Anna Salai Corridor"

    async def test_get_zone_case_insensitive(self, client):
        r = await client.get("/api/traffic/zones/z3")
        assert r.status_code == 200
        assert r.json()["zone_id"] == "Z3"

    async def test_get_zone_not_found(self, client):
        r = await client.get("/api/traffic/zones/Z99")
        assert r.status_code == 404

    async def test_metrics_endpoint(self, client):
        r = await client.get("/api/traffic/metrics")
        assert r.status_code == 200
        d = r.json()
        assert "total_vehicles" in d
        assert "flow_efficiency" in d
        assert "avg_delay_min" in d
        assert "active_incidents" in d
        assert "adaptive_signals" in d

    async def test_routes_default(self, client):
        r = await client.get("/api/traffic/routes")
        assert r.status_code == 200
        d = r.json()
        assert "options" in d
        assert len(d["options"]) == 4
        # Should be sorted by ETA (rank 1 fastest)
        etas = [o["eta_min"] for o in d["options"]]
        assert etas == sorted(etas), "Routes should be sorted by ETA"
        assert d["options"][0]["status"] == "OPTIMAL"

    async def test_routes_with_params(self, client):
        r = await client.get("/api/traffic/routes?origin=T.Nagar&destination=Airport")
        assert r.status_code == 200
        d = r.json()
        assert d["origin"] == "T.Nagar"
        assert d["destination"] == "Airport"


# ══════════════════════════════════════════════════════════
# IoT SENSOR INGESTION
# ══════════════════════════════════════════════════════════

class TestSensorIngestion:
    async def test_valid_sensor_reading(self, client):
        r = await client.post("/api/traffic/sensor", params={
            "sensor_id":     "SNS-TEST-01",
            "zone_id":       "Z1",
            "vehicle_count": 250,
            "avg_speed_ms":  12.5,
            "occupancy_pct": 62.0,
            "wait_time_s":   18.0,
            "co2_mgs":       2100.0,
            "noise_db":      67.5,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "accepted"
        assert d["zone_id"] == "Z1"
        assert d["sensor_id"] == "SNS-TEST-01"

    async def test_sensor_updates_zone_state(self, client):
        # Push a specific occupancy value
        await client.post("/api/traffic/sensor", params={
            "sensor_id":     "SNS-TEST-02",
            "zone_id":       "Z4",
            "vehicle_count": 150,
            "avg_speed_ms":  19.0,
            "occupancy_pct": 20.0,  # very low
            "wait_time_s":   3.0,
        })
        r = await client.get("/api/traffic/zones/Z4")
        assert r.status_code == 200
        z = r.json()
        # Congestion should reflect the reading (0.20)
        assert z["congestion"] < 0.5, "Low occupancy should reduce congestion"

    async def test_sensor_invalid_zone(self, client):
        r = await client.post("/api/traffic/sensor", params={
            "sensor_id":     "SNS-BAD",
            "zone_id":       "Z99",
            "vehicle_count": 100,
            "avg_speed_ms":  15.0,
            "occupancy_pct": 50.0,
        })
        assert r.status_code == 400

    async def test_telemetry_endpoint(self, client):
        r = await client.get("/api/traffic/telemetry/Z3")
        assert r.status_code == 200
        d = r.json()
        for field in ["vehicle_id", "lane_id", "speed_ms", "wait_time_s",
                      "co2_mgs", "nox_mgs", "fuel_mls", "noise_db"]:
            assert field in d, f"Missing telemetry field: {field}"

    async def test_telemetry_not_found(self, client):
        r = await client.get("/api/traffic/telemetry/Z99")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════
# SIMULATION CONTROL
# ══════════════════════════════════════════════════════════

class TestSimControl:
    async def test_sim_status(self, client):
        r = await client.get("/api/traffic/sim/status")
        assert r.status_code == 200
        d = r.json()
        assert "running" in d
        assert "sim_time" in d

    async def test_pause_and_run(self, client):
        await client.post("/api/traffic/sim/pause")
        r = await client.get("/api/traffic/sim/status")
        # (running state toggled)
        assert r.status_code == 200
        # Resume
        await client.post("/api/traffic/sim/run")
        r = await client.get("/api/traffic/sim/status")
        assert r.json()["running"] is True

    async def test_reset(self, client):
        await client.post("/api/traffic/sim/reset")
        r = await client.get("/api/traffic/sim/status")
        assert r.json()["sim_time"] == 0
        assert r.json()["sim_step"] == 0
        # Resume for subsequent tests
        await client.post("/api/traffic/sim/run")


# ══════════════════════════════════════════════════════════
# SIGNALS
# ══════════════════════════════════════════════════════════

class TestSignals:
    async def test_list_all_signals(self, client):
        r = await client.get("/api/signals/")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 12
        assert len(d["signals"]) == 12

    async def test_signal_fields(self, client):
        r = await client.get("/api/signals/")
        s = r.json()["signals"][0]
        for field in ["signal_id", "intersection", "zone_id",
                      "phase", "green_s", "adaptive"]:
            assert field in s, f"Missing signal field: {field}"

    async def test_phase_valid_enum(self, client):
        r = await client.get("/api/signals/")
        for s in r.json()["signals"]:
            assert s["phase"] in ("G", "Y", "R"), f"Bad phase: {s['phase']}"

    async def test_filter_by_zone(self, client):
        r = await client.get("/api/signals/?zone_id=Z1")
        assert r.status_code == 200
        for s in r.json()["signals"]:
            assert s["zone_id"] == "Z1"

    async def test_get_single_signal(self, client):
        r = await client.get("/api/signals/SIG-A01")
        assert r.status_code == 200
        d = r.json()
        assert d["signal_id"] == "SIG-A01"

    async def test_get_signal_not_found(self, client):
        r = await client.get("/api/signals/SIG-ZZ99")
        assert r.status_code == 404

    async def test_manual_override(self, client):
        r = await client.put("/api/signals/SIG-A01", json={
            "green_s": 75,
            "reason":  "test override"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["green_s"] == 75
        assert d["adaptive"] is False

    async def test_restore_adaptive(self, client):
        r = await client.post("/api/signals/SIG-A01/reset")
        assert r.status_code == 200
        assert r.json()["status"] == "adaptive_restored"
        # Verify adaptive restored
        r2 = await client.get("/api/signals/SIG-A01")
        assert r2.json()["adaptive"] is True

    async def test_bulk_update(self, client):
        r = await client.post("/api/signals/bulk-update", json={
            "updates": [
                {"signal_id": "SIG-B07", "green_s": 60},
                {"signal_id": "SIG-C05", "green_s": 70},
            ]
        })
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 2
        assert all(res["status"] == "updated" for res in results)

    async def test_optimize_endpoint(self, client):
        r = await client.get("/api/signals/optimize")
        assert r.status_code == 200
        d = r.json()
        assert "recommendations" in d
        assert len(d["recommendations"]) == 12
        rec = d["recommendations"][0]
        for field in ["signal_id", "current_green_s", "recommended_green_s",
                      "delta_s", "reasoning"]:
            assert field in rec

    async def test_green_s_in_valid_range(self, client):
        r = await client.get("/api/signals/optimize")
        for rec in r.json()["recommendations"]:
            assert 15 <= rec["recommended_green_s"] <= 90


# ══════════════════════════════════════════════════════════
# AI / LLM CHAT
# ══════════════════════════════════════════════════════════

class TestAIChat:
    async def test_chat_basic(self, client):
        r = await client.post("/api/ai/chat", json={
            "message": "What is the current traffic status?"
        })
        assert r.status_code == 200
        d = r.json()
        assert "reply" in d
        assert len(d["reply"]) > 20
        assert "intent" in d
        assert d["intent"] in ("status_query", "general", "route_query",
                               "signal_control", "prediction", "emergency", "explanation")

    async def test_chat_route_query(self, client):
        r = await client.post("/api/ai/chat", json={
            "message": "What is the fastest route to the airport?"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["intent"] == "route_query"
        assert len(d["actions"]) > 0

    async def test_chat_signal_query(self, client):
        r = await client.post("/api/ai/chat", json={
            "message": "How are the traffic signals being controlled?"
        })
        assert r.status_code == 200
        assert r.json()["intent"] == "signal_control"

    async def test_chat_explanation(self, client):
        r = await client.post("/api/ai/chat", json={
            "message": "Explain how the AI system works"
        })
        assert r.status_code == 200
        assert r.json()["intent"] == "explanation"

    async def test_chat_with_history(self, client):
        r = await client.post("/api/ai/chat", json={
            "message": "And what about the signals in Z3?",
            "history": [
                {"role": "user",      "content": "What is the traffic status?"},
                {"role": "assistant", "content": "Traffic efficiency is 74%."},
            ]
        })
        assert r.status_code == 200
        assert "reply" in r.json()

    async def test_chat_has_latency_field(self, client):
        r = await client.post("/api/ai/chat", json={"message": "Hello"})
        assert "latency_ms" in r.json()
        assert r.json()["latency_ms"] >= 0

    async def test_predict_single_zone(self, client):
        r = await client.get("/api/ai/predict/Z3")
        assert r.status_code == 200
        d = r.json()
        assert d["zone_id"] == "Z3"
        assert "predicted_congestion" in d
        assert "recommendation" in d
        assert 0 <= d["confidence"] <= 1
        assert d["horizon_min"] == 60

    async def test_predict_all_zones(self, client):
        r = await client.get("/api/ai/predict")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 12
        # Should be sorted by predicted congestion desc
        preds = [p["predicted_congestion"] for p in d["predictions"]]
        assert preds == sorted(preds, reverse=True)

    async def test_predict_invalid_zone(self, client):
        r = await client.get("/api/ai/predict/Z99")
        assert r.status_code == 404

    async def test_city_summary(self, client):
        r = await client.get("/api/ai/summary")
        assert r.status_code == 200
        d = r.json()
        assert "summary" in d
        assert len(d["summary"]) > 50
        assert "metrics" in d
        assert "worst_zones" in d

    async def test_explain_system(self, client):
        r = await client.get("/api/ai/explain")
        assert r.status_code == 200
        d = r.json()
        assert "sections" in d
        assert len(d["sections"]) >= 5
        # Each section should have heading + text
        for sec in d["sections"]:
            assert "heading" in sec
            assert "text" in sec
            assert len(sec["text"]) > 20

    async def test_signal_optimize_ai(self, client):
        r = await client.get("/api/ai/signal-optimize")
        assert r.status_code == 200
        d = r.json()
        assert "recommendations" in d
        assert "summary" in d


# ══════════════════════════════════════════════════════════
# EMERGENCY
# ══════════════════════════════════════════════════════════

class TestEmergency:
    async def test_no_active_emergency_initially(self, client):
        # Clear any existing
        await client.post("/api/emergency/deactivate")
        r = await client.get("/api/emergency/active")
        assert r.status_code == 200
        assert r.json()["status"] == "none"

    async def test_activate_ambulance(self, client):
        r = await client.post("/api/emergency/activate", json={
            "emergency_type": "ambulance",
            "origin":         "T.Nagar",
            "destination":    "Apollo Hospital",
            "notes":          "Cardiac patient",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["emergency_type"] == "ambulance"
        assert d["status"] == "ACTIVE"
        assert len(d["corridor"]) > 0
        assert d["eta_min"] == 8

    async def test_active_emergency_readable(self, client):
        r = await client.get("/api/emergency/active")
        assert r.status_code == 200
        d = r.json()
        assert d["emergency_type"] == "ambulance"

    async def test_corridor_signals_set_to_green(self, client):
        emg = (await client.get("/api/emergency/active")).json()
        for sid in emg["corridor"]:
            r = await client.get(f"/api/signals/{sid}")
            assert r.status_code == 200
            s = r.json()
            assert s["phase"] == "G"
            assert s["adaptive"] is False
            assert s["green_s"] == 120

    async def test_deactivate_emergency(self, client):
        r = await client.post("/api/emergency/deactivate")
        assert r.status_code == 200
        assert r.json()["status"] == "RESOLVED"

    async def test_signals_restored_after_deactivate(self, client):
        r = await client.get("/api/signals/SIG-A01")
        assert r.json()["adaptive"] is True

    async def test_activate_lockdown(self, client):
        r = await client.post("/api/emergency/activate", json={
            "emergency_type": "lockdown"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["emergency_type"] == "lockdown"
        # All 12 signals in corridor
        assert len(d["corridor"]) == 12

    async def test_lockdown_all_signals_red(self, client):
        r = await client.get("/api/signals/")
        for s in r.json()["signals"]:
            assert s["phase"] == "R"
            assert s["adaptive"] is False

    async def test_clear_lockdown(self, client):
        await client.post("/api/emergency/deactivate")
        r = await client.get("/api/emergency/active")
        assert r.json()["status"] == "none"

    async def test_emergency_history(self, client):
        r = await client.get("/api/emergency/history")
        assert r.status_code == 200
        d = r.json()
        assert "incidents" in d
        assert d["total"] >= 2  # at least ambulance + lockdown from above

    async def test_invalid_emergency_type(self, client):
        r = await client.post("/api/emergency/activate", json={
            "emergency_type": "zombie_apocalypse"
        })
        assert r.status_code == 400

    async def test_double_deactivate_errors(self, client):
        r = await client.post("/api/emergency/deactivate")
        assert r.status_code == 400  # Nothing active


# ══════════════════════════════════════════════════════════
# ALERTS
# ══════════════════════════════════════════════════════════

class TestAlerts:
    async def test_list_alerts(self, client):
        r = await client.get("/api/alerts/")
        assert r.status_code == 200
        d = r.json()
        assert "alerts" in d
        assert "total" in d
        assert "unresolved" in d

    async def test_alert_fields(self, client):
        r = await client.get("/api/alerts/")
        if r.json()["total"] > 0:
            a = r.json()["alerts"][0]
            for f in ["alert_id", "level", "alert_type", "message", "timestamp"]:
                assert f in a

    async def test_filter_by_level(self, client):
        # Create a known alert first
        await client.post("/api/alerts/", json={
            "level": "critical", "alert_type": "TEST", "message": "Unit test alert"
        })
        r = await client.get("/api/alerts/?level=critical")
        assert r.status_code == 200
        for a in r.json()["alerts"]:
            assert a["level"] == "critical"

    async def test_create_alert(self, client):
        r = await client.post("/api/alerts/", json={
            "level":      "info",
            "alert_type": "SYSTEM",
            "message":    "Test alert from unit tests",
            "zone_id":    "Z5",
        })
        assert r.status_code == 200
        a = r.json()["alert"]
        assert a["level"] == "info"
        assert a["zone_id"] == "Z5"

    async def test_alert_stats(self, client):
        r = await client.get("/api/alerts/stats")
        assert r.status_code == 200
        d = r.json()
        assert "by_level" in d
        assert "by_type" in d
        assert "total" in d

    async def test_resolve_alert(self, client):
        # Get first unresolved alert
        r = await client.get("/api/alerts/?resolved=false&limit=1")
        alerts = r.json()["alerts"]
        if alerts:
            aid = alerts[0]["alert_id"]
            r2 = await client.put(f"/api/alerts/{aid}/resolve")
            assert r2.status_code == 200
            assert r2.json()["status"] == "resolved"

    async def test_resolve_nonexistent(self, client):
        r = await client.put("/api/alerts/XXXXXX/resolve")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════

class TestAnalytics:
    async def test_daily_summary(self, client):
        r = await client.get("/api/analytics/daily")
        assert r.status_code == 200
        d = r.json()
        assert "date" in d
        assert "total_vehicles" in d
        assert "hourly" in d
        assert len(d["hourly"]) == 24

    async def test_hourly_has_24_buckets(self, client):
        r = await client.get("/api/analytics/hourly")
        assert r.status_code == 200
        h = r.json()["hourly"]
        assert len(h) == 24
        hours = [b["hour"] for b in h]
        assert hours == list(range(24))

    async def test_heatmap(self, client):
        r = await client.get("/api/analytics/heatmap")
        assert r.status_code == 200
        d = r.json()
        assert len(d["zones"]) == 12
        z = d["zones"][0]
        for f in ["zone_id", "name", "congestion", "status"]:
            assert f in z

    async def test_efficiency_trend_default(self, client):
        r = await client.get("/api/analytics/efficiency")
        assert r.status_code == 200
        d = r.json()
        assert d["days"] == 7
        assert len(d["trend"]) == 7
        assert "avg_efficiency" in d

    async def test_efficiency_trend_custom_days(self, client):
        r = await client.get("/api/analytics/efficiency?days=14")
        assert r.status_code == 200
        assert r.json()["days"] == 14
        assert len(r.json()["trend"]) == 14

    async def test_signal_performance(self, client):
        r = await client.get("/api/analytics/signals/perf")
        assert r.status_code == 200
        d = r.json()
        assert len(d["signals"]) == 12
        s = d["signals"][0]
        for f in ["signal_id", "green_pct", "throughput_vph", "adaptive"]:
            assert f in s

    async def test_environmental_impact(self, client):
        r = await client.get("/api/analytics/environment")
        assert r.status_code == 200
        d = r.json()
        for f in ["fuel_saved_l_day", "co2_reduced_kg_day", "vehicles_tracked"]:
            assert f in d
        assert d["fuel_saved_l_day"] > 0
        assert d["co2_reduced_kg_day"] > 0
