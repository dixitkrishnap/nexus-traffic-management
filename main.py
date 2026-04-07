"""
main.py
NEXUS Traffic Intelligence System â€” Backend Entry Point

Run:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

API docs: http://localhost:8000/docs
WebSocket: ws://localhost:8000/api/traffic/ws
"""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from db.database import init_db
from services.iot_sensor import sensor_engine_loop, signal_engine_loop
from api.routes import traffic, signals, ai_chat, emergency, alerts, analytics


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LIFESPAN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n{'='*55}")
    print(f"  NEXUS Traffic Intelligence System v{settings.VERSION}")
    print(f"  Environment : {settings.APP_ENV}")
    print(f"  LLM Model   : {settings.LLM_MODEL}")
    print(f"  API Key set : {'YES âœ…' if settings.ANTHROPIC_API_KEY else 'NO  âš ï¸  (demo mode)'}")
    print(f"{'='*55}\n")

    # Init DB
    await init_db()

    # Start background engines
    sensor_task = asyncio.create_task(sensor_engine_loop())
    signal_task = asyncio.create_task(signal_engine_loop())
    print("ðŸš€  All engines running. API ready.\n")

    yield

    sensor_task.cancel()
    signal_task.cancel()
    print("ðŸ›‘  NEXUS shutting down.")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# APP
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app = FastAPI(
    title       = settings.APP_NAME,
    description = (
        "Real-time AI + IoT Traffic Management System for Chennai Metro. "
        "Powered by 48 IoT sensor nodes, 12 adaptive signal controllers, "
        "and Claude LLM for natural language interaction and signal optimisation."
    ),
    version     = settings.VERSION,
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.mount("/static", StaticFiles(directory="."), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ROUTERS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.include_router(traffic.router,   prefix="/api/traffic",   tags=["Traffic & Zones"])
app.include_router(signals.router,   prefix="/api/signals",   tags=["Signal Control"])
app.include_router(ai_chat.router,   prefix="/api/ai",        tags=["AI / LLM"])
app.include_router(emergency.router, prefix="/api/emergency", tags=["Emergency"])
app.include_router(alerts.router,    prefix="/api/alerts",    tags=["Alerts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HEALTH & ROOT
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/", response_class=HTMLResponse, tags=["Health"])
async def root():
    return """
    <html><head><title>NEXUS Backend</title>
    <style>body{font-family:monospace;background:#0a0e17;color:#e2e8f0;padding:40px;}
    a{color:#22c55e;}h1{color:#fff;}pre{color:#64748b;}</style></head>
    <body>
    <h1>NEXUS Traffic Intelligence System</h1>
    <p>Backend is online. Version 2.0.0</p>
    <p><a href="/docs">ðŸ“– Interactive API Docs (Swagger)</a></p>
    <p><a href="/redoc">ðŸ“‹ ReDoc API Reference</a></p>
    <p><a href="/api/traffic/metrics">ðŸ“Š Live Metrics JSON</a></p>
    <p><a href="/api/ai/explain">ðŸ¤– How NEXUS Works (plain English)</a></p>
    <pre>WebSocket: ws://localhost:8000/api/traffic/ws</pre>
    </body></html>
    """


@app.get("/health", tags=["Health"])
async def health():
    from services.state_store import store
    m = store.get_metrics()
    return {
        "status":   "healthy",
        "version":  settings.VERSION,
        "env":      settings.APP_ENV,
        "llm":      "live" if settings.ANTHROPIC_API_KEY else "demo",
        "running":  store.running,
        "metrics":  m,
        "services": {
            "sensor_engine":  "running",
            "signal_engine":  "running",
            "llm_engine":     "live" if settings.ANTHROPIC_API_KEY else "demo",
            "database":       "sqlite",
            "websocket":      "ready",
        },
    }
