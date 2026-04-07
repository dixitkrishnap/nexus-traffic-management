"""
db/database.py
Async SQLite via aiosqlite.
Swap DATABASE_URL to postgresql+asyncpg for production.
"""

from __future__ import annotations
import aiosqlite
import json
from datetime import datetime, timezone
from core.config import settings

DB_PATH = "nexus.db"


# ──────────────────────────────────────────────────────────
# INIT
# ──────────────────────────────────────────────────────────

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        -- ── Zones ────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS zones (
            zone_id      TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            lat          REAL DEFAULT 0,
            lng          REAL DEFAULT 0,
            base_cong    REAL DEFAULT 0.5,
            num_sensors  INTEGER DEFAULT 4,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        -- ── Sensor readings (time-series) ─────────────────
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id      TEXT NOT NULL,
            zone_id        TEXT NOT NULL,
            timestamp      TEXT NOT NULL,
            vehicle_count  INTEGER DEFAULT 0,
            avg_speed_ms   REAL DEFAULT 0,
            occupancy_pct  REAL DEFAULT 0,
            wait_time_s    REAL DEFAULT 0,
            weather        TEXT DEFAULT 'clear',
            co2_mgs        REAL DEFAULT 0,
            nox_mgs        REAL DEFAULT 0,
            fuel_mls       REAL DEFAULT 0,
            noise_db       REAL DEFAULT 0,
            FOREIGN KEY(zone_id) REFERENCES zones(zone_id)
        );
        CREATE INDEX IF NOT EXISTS idx_sensor_zone_ts ON sensor_readings(zone_id, timestamp DESC);

        -- ── Signals ───────────────────────────────────────
        CREATE TABLE IF NOT EXISTS signals (
            signal_id    TEXT PRIMARY KEY,
            intersection TEXT NOT NULL,
            zone_id      TEXT NOT NULL,
            phase        TEXT DEFAULT 'G',
            green_s      INTEGER DEFAULT 45,
            yellow_s     INTEGER DEFAULT 4,
            red_s        INTEGER DEFAULT 55,
            adaptive     INTEGER DEFAULT 1,
            cycle_count  INTEGER DEFAULT 0,
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        -- ── Alerts ────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id    TEXT PRIMARY KEY,
            level       TEXT NOT NULL,
            alert_type  TEXT NOT NULL,
            message     TEXT NOT NULL,
            zone_id     TEXT,
            timestamp   TEXT NOT NULL,
            resolved    INTEGER DEFAULT 0,
            resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp DESC);

        -- ── Emergency incidents ───────────────────────────
        CREATE TABLE IF NOT EXISTS emergency_incidents (
            incident_id     TEXT PRIMARY KEY,
            emergency_type  TEXT NOT NULL,
            origin          TEXT,
            destination     TEXT,
            vehicle_id      TEXT,
            status          TEXT DEFAULT 'ACTIVE',
            corridor        TEXT,
            eta_min         INTEGER,
            notes           TEXT,
            activated_at    TEXT NOT NULL,
            resolved_at     TEXT
        );

        -- ── Chat history ──────────────────────────────────
        CREATE TABLE IF NOT EXISTS chat_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            intent     TEXT,
            actions    TEXT,
            timestamp  TEXT DEFAULT (datetime('now'))
        );

        -- ── Analytics daily rollup ────────────────────────
        CREATE TABLE IF NOT EXISTS analytics_daily (
            date            TEXT PRIMARY KEY,
            total_vehicles  INTEGER DEFAULT 0,
            peak_hour       INTEGER DEFAULT 17,
            avg_efficiency  REAL DEFAULT 0,
            total_incidents INTEGER DEFAULT 0,
            fuel_saved_l    REAL DEFAULT 0,
            co2_reduced_kg  REAL DEFAULT 0,
            hourly_json     TEXT DEFAULT '[]'
        );

        -- ── LLM decisions log ─────────────────────────────
        CREATE TABLE IF NOT EXISTS llm_decisions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            trigger      TEXT NOT NULL,
            context_json TEXT,
            decision     TEXT,
            actions_json TEXT,
            latency_ms   INTEGER
        );
        """)

        # Seed zones if empty
        cur = await db.execute("SELECT COUNT(*) FROM zones")
        (n,) = await cur.fetchone()
        if n == 0:
            await _seed_zones(db)
            await _seed_signals(db)

        await db.commit()

    print("✅  Database initialised.")


async def _seed_zones(db: aiosqlite.Connection) -> None:
    zones = [
        ("Z1",  "Anna Salai Corridor",    13.0674, 80.2376, 0.55),
        ("Z2",  "OMR Tech Park",          12.9120, 80.2284, 0.40),
        ("Z3",  "T.Nagar Market Hub",     13.0418, 80.2341, 0.75),
        ("Z4",  "Airport Expressway",     12.9900, 80.1637, 0.25),
        ("Z5",  "Tambaram Junction",      12.9249, 80.1000, 0.60),
        ("Z6",  "Adyar Bridge",           13.0012, 80.2565, 0.35),
        ("Z7",  "Guindy Industrial",      13.0067, 80.2206, 0.50),
        ("Z8",  "Velachery Roundabout",   12.9750, 80.2209, 0.65),
        ("Z9",  "Koyambedu Terminus",     13.0694, 80.1948, 0.70),
        ("Z10", "Porur Junction",         13.0337, 80.1567, 0.45),
        ("Z11", "Sholinganallur Signal",  12.8996, 80.2271, 0.55),
        ("Z12", "Chromepet Crossroads",   12.9516, 80.1462, 0.30),
    ]
    await db.executemany(
        "INSERT INTO zones(zone_id,name,lat,lng,base_cong) VALUES(?,?,?,?,?)", zones
    )
    print("🌱  Zones seeded.")


async def _seed_signals(db: aiosqlite.Connection) -> None:
    sigs = [
        ("SIG-A01", "Anna Salai / Mount Rd",     "Z1",  45, 55),
        ("SIG-A02", "Anna Salai / Nandanam",     "Z1",  40, 50),
        ("SIG-A14", "T.Nagar / Panagal Park",    "Z3",  35, 45),
        ("SIG-B07", "OMR / Perungudi Jn",        "Z2",  50, 60),
        ("SIG-B12", "OMR / Sholinganallur",      "Z11", 45, 55),
        ("SIG-C22", "Adyar / LB Road",           "Z6",  40, 50),
        ("SIG-C05", "Airport / Meenambakkam",    "Z4",  55, 65),
        ("SIG-D03", "Koyambedu / NH-48",         "Z9",  35, 45),
        ("SIG-D11", "Guindy / Sardar Patel Rd",  "Z7",  45, 55),
        ("SIG-E08", "Velachery / 100 Ft Rd",     "Z8",  40, 50),
        ("SIG-E14", "Tambaram / GST Rd",         "Z5",  50, 60),
        ("SIG-F02", "Porur / Arcot Rd",          "Z10", 45, 55),
    ]
    await db.executemany(
        "INSERT INTO signals(signal_id,intersection,zone_id,green_s,red_s) VALUES(?,?,?,?,?)",
        sigs
    )
    print("🚦  Signals seeded.")


# ──────────────────────────────────────────────────────────
# DEPENDENCY
# ──────────────────────────────────────────────────────────

async def get_db():
    """FastAPI dependency — yields an open aiosqlite connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
