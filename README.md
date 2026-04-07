<<<<<<< HEAD
# Nexus-Traffic-Management-
=======
# NEXUS — Traffic Intelligence System Backend

**Real-time AI + IoT Traffic Management for Chennai Metro**

A production-ready FastAPI backend powering 12 traffic zones, 48 IoT sensor nodes, 12 adaptive signal controllers, and a Claude LLM natural language interface.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend Pages                        │
│   index.html │ page2_map.html │ page3_control.html      │
│               page4_results.html                        │
└───────────────────────┬─────────────────────────────────┘
                        │  REST API + WebSocket
┌───────────────────────▼─────────────────────────────────┐
│                  FastAPI Backend                         │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ IoT Sensor   │  │ Signal       │  │ LLM Engine   │  │
│  │ Engine       │  │ Engine       │  │ (Claude AI)  │  │
│  │ 5s tick      │  │ 1.1s tick    │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│  ┌──────▼─────────────────▼──────────────────▼───────┐  │
│  │              State Store (in-memory)               │  │
│  │   zones │ signals │ alerts │ emergency             │  │
│  └──────────────────────────┬──────────────────────┘  │
│                             │ WebSocket fan-out        │
│  ┌──────────────────────────▼──────────────────────┐   │
│  │              SQLite Database                    │   │
│  │  sensor_readings │ alerts │ chat_history        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Prerequisites

```bash
Python 3.11+
```

### 2. Install dependencies

```bash
cd nexus_backend
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

> **Without an API key**, the system runs in demo mode with smart deterministic responses. All other features work identically.

### 4. Start the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:

```
═══════════════════════════════════════════════════════
  NEXUS Traffic Intelligence System v2.0.0
  Environment : development
  LLM Model   : claude-sonnet-4-20250514
  API Key set : YES ✅
═══════════════════════════════════════════════════════

✅  Database initialised.
🌡️   Sensor engine started (interval=5s)
🚦  Signal engine started (tick=1.1s)
🚀  All engines running. API ready.
```

### 5. Explore

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Landing page |
| http://localhost:8000/docs | Interactive Swagger API docs |
| http://localhost:8000/redoc | ReDoc API reference |
| http://localhost:8000/health | System health check |
| ws://localhost:8000/api/traffic/ws | WebSocket live feed |

---

## Running the Demo

```bash
# Full demo of all 10 API capabilities
python scripts/demo_client.py

# Real-time WebSocket terminal monitor
python scripts/ws_monitor.py
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v --asyncio-mode=auto
```

Expected: **50+ tests passing**, covering every endpoint.

---

## API Reference

### Traffic & Zones

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/traffic/zones` | All 12 zone snapshots |
| GET | `/api/traffic/zones/{id}` | Single zone (Z1–Z12) |
| GET | `/api/traffic/metrics` | System-wide KPIs |
| GET | `/api/traffic/routes` | Route optimizer |
| POST | `/api/traffic/sensor` | IoT sensor ingestion |
| GET | `/api/traffic/telemetry/{zone}` | SUMO vehicle telemetry |
| POST | `/api/traffic/sim/run` | Start simulation |
| POST | `/api/traffic/sim/pause` | Pause/resume |
| POST | `/api/traffic/sim/reset` | Reset to t=0 |
| WS | `/api/traffic/ws` | Live WebSocket feed |

### Signal Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/signals/` | All 12 signal states |
| GET | `/api/signals/{id}` | Single signal |
| PUT | `/api/signals/{id}` | Manual timing override |
| POST | `/api/signals/{id}/reset` | Restore adaptive |
| POST | `/api/signals/bulk-update` | Batch apply timings |
| GET | `/api/signals/optimize` | LLM recommendations |

### AI / LLM

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/chat` | Natural language query |
| GET | `/api/ai/predict/{zone}` | 60-min prediction |
| GET | `/api/ai/predict` | All-zone predictions |
| GET | `/api/ai/summary` | Plain-English city status |
| GET | `/api/ai/explain` | How the system works |
| GET | `/api/ai/signal-optimize` | LLM signal advice |

### Emergency

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/emergency/activate` | Activate corridor |
| GET | `/api/emergency/active` | Current status |
| POST | `/api/emergency/deactivate` | Clear emergency |
| GET | `/api/emergency/history` | Past incidents |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alerts/` | Paginated feed |
| GET | `/api/alerts/stats` | Level/type breakdown |
| POST | `/api/alerts/` | Manual alert |
| PUT | `/api/alerts/{id}/resolve` | Resolve alert |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/daily` | Today's stats |
| GET | `/api/analytics/hourly` | 24-hour volume curve |
| GET | `/api/analytics/heatmap` | Zone congestion map |
| GET | `/api/analytics/efficiency` | N-day trend |
| GET | `/api/analytics/signals/perf` | Signal performance |
| GET | `/api/analytics/environment` | Environmental impact |

---

## WebSocket Live Feed

Connect: `ws://localhost:8000/api/traffic/ws`

On connect, you immediately receive a full state snapshot. Subsequent messages arrive every 5 seconds.

### Message types

```json
// State update (every 5 seconds)
{
  "type": "state_update",
  "metrics": { "total_vehicles": 2841, "flow_efficiency": 74.2, ... },
  "zones":   [ { "zone_id": "Z1", "congestion": 0.55, ... }, ... ],
  "signals": [ { "signal_id": "SIG-A01", "phase": "G", ... }, ... ],
  "alerts":  [ { "alert_id": "A1B2C3", "level": "warning", ... } ],
  "emergency": null,
  "sim_time": 45,
  "sim_step": 9
}

// Emergency activated
{ "type": "emergency", "payload": { "emergency_type": "ambulance", ... } }

// Emergency cleared
{ "type": "emergency_cleared", "payload": { ... } }

// Heartbeat (every 30s if no state update)
{ "type": "ping", "ts": "2025-10-01T08:30:00Z" }
```

### Connecting from the frontend pages

Add this to any frontend page to get live updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/traffic/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'state_update') {
    // data.zones     — array of zone objects
    // data.signals   — array of signal objects
    // data.metrics   — system KPIs
    // data.alerts    — recent alerts
    updateDashboard(data);
  }
};
```

---

## IoT Sensor Integration (Production)

The `/api/traffic/sensor` endpoint accepts readings from physical sensor nodes. In production, replace the simulation loop in `services/iot_sensor.py` with one of:

**MQTT (recommended for hardware):**
```python
# In services/iot_sensor.py, replace sensor_engine_loop with:
async with asyncio_mqtt.Client("mqtt://your-broker") as client:
    async with client.messages() as messages:
        await client.subscribe("nexus/sensors/#")
        async for msg in messages:
            data = json.loads(msg.payload)
            store.apply_sensor_reading(data["zone_id"], data)
```

**Direct HTTP from Raspberry Pi / Arduino:**
```python
# On the sensor hardware, POST to:
requests.post("http://nexus-server:8000/api/traffic/sensor", params={
    "sensor_id":     "SNS-Z1-01",
    "zone_id":       "Z1",
    "vehicle_count": count,
    "avg_speed_ms":  speed,
    "occupancy_pct": occupancy,
    "wait_time_s":   wait_time,
    "co2_mgs":       co2,
    "noise_db":      noise_level,
})
```

---

## Production Deployment

| Component | Development | Production |
|-----------|-------------|------------|
| Database | SQLite (aiosqlite) | PostgreSQL + TimescaleDB |
| State store | In-memory dict | Redis |
| IoT ingestion | Simulation loop | MQTT broker (Mosquitto) |
| Server | uvicorn single process | gunicorn + uvicorn workers |
| Reverse proxy | — | nginx |
| Monitoring | — | Prometheus + Grafana |

---

## How the AI Works (for judges)

1. **IoT sensors** collect data every 5 seconds: vehicle count, speed (m/s), lane occupancy %, waiting time, CO₂, NOx emissions

2. **Sensor engine** merges readings into live zone state. If occupancy crosses 55% → WARNING alert. If 75% → CRITICAL alert.

3. **Signal engine** advances phase timers every 1.1 seconds. On each GREEN→YELLOW→RED→GREEN cycle, if `adaptive=True`, the next GREEN duration is recalculated:
   ```
   green_s = 15 + congestion × (90 - 15)
   ```
   So a 80%-congested junction gets 75s green. A 20%-congested one gets 30s.

4. **LLM engine** (Claude Sonnet): every chat query injects the full live snapshot as context. Claude reasons over real sensor data to answer in plain English, predict surges, and recommend signal adjustments.

5. **WebSocket** broadcasts full state to all connected frontend clients every 5 seconds.

---

## File Structure

```
nexus_backend/
├── main.py                    # FastAPI app, lifespan, routers
├── requirements.txt
├── .env.example
├── nexus.db                   # Auto-created on first run
│
├── core/
│   └── config.py              # Pydantic-settings config
│
├── db/
│   └── database.py            # SQLite init + seed data
│
├── models/
│   └── schemas.py             # All Pydantic schemas
│
├── services/
│   ├── state_store.py         # In-memory live state + WebSocket pub/sub
│   ├── iot_sensor.py          # IoT sensor simulation + signal tick
│   └── llm_engine.py         # Anthropic Claude integration
│
├── api/routes/
│   ├── traffic.py             # Zones, metrics, routes, WebSocket
│   ├── signals.py             # Signal control + LLM optimize
│   ├── ai_chat.py             # Chat, predictions, explain
│   ├── emergency.py           # Corridor activation
│   ├── alerts.py              # Alert feed
│   └── analytics.py           # Daily/hourly/heatmap/environment
│
├── tests/
│   └── test_api.py            # 50+ async tests
│
└── scripts/
    ├── demo_client.py         # Full 10-section demo
    └── ws_monitor.py          # WebSocket terminal monitor
```
>>>>>>> 3e279d9 (Initial commit - NEXUS ATMS)
