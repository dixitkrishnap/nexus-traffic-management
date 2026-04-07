"""
core/config.py
Central configuration loaded from environment / .env file.
"""

from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
import json


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────────
    APP_NAME: str = "NEXUS Traffic Intelligence System"
    APP_ENV:  str = "development"
    DEBUG:    bool = True
    VERSION:  str = "2.0.0"

    # ── Server ─────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Database ───────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./nexus.db"

    # ── Anthropic LLM ──────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL:         str = "claude-sonnet-4-20250514"
    LLM_MAX_TOKENS:    int = 1024

    # ── IoT / Sensors ──────────────────────────────────────
    SENSOR_POLL_INTERVAL_S: int   = 5
    IOT_SIMULATE:           bool  = True
    MQTT_HOST:              str   = "localhost"
    MQTT_PORT:              int   = 1883
    MQTT_TOPIC_PREFIX:      str   = "nexus/sensors/"

    # ── Traffic Engine ─────────────────────────────────────
    CONGESTION_WARN_THRESHOLD: float = 0.55
    CONGESTION_CRIT_THRESHOLD: float = 0.75
    SIGNAL_MIN_GREEN_S:        int   = 15
    SIGNAL_MAX_GREEN_S:        int   = 90
    SIGNAL_YELLOW_S:           int   = 4

    # ── Alerts ─────────────────────────────────────────────
    ALERT_RETENTION_HOURS: int = 24

    # ── Emergency ──────────────────────────────────────────
    EMERGENCY_CORRIDOR_TIMEOUT_S: int = 300

    # ── CORS ───────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
