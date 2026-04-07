"""
models/schemas.py
All Pydantic request/response models for the NEXUS API.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ──────────────────────────────────────────────────────────
# ENUMS
# ──────────────────────────────────────────────────────────

class ZoneStatus(str, Enum):
    NORMAL   = "normal"
    WARNING  = "warning"
    CRITICAL = "critical"

class SignalPhase(str, Enum):
    GREEN  = "G"
    YELLOW = "Y"
    RED    = "R"

class AlertLevel(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"
    SUCCESS  = "success"

class AlertType(str, Enum):
    CONGESTION     = "CONGESTION"
    ACCIDENT       = "ACCIDENT"
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    WEATHER        = "WEATHER"
    ROUTE_OPT      = "ROUTE_OPTIMIZED"
    EMERGENCY      = "EMERGENCY"
    SYSTEM         = "SYSTEM"
    IOT_ALERT      = "IOT_ALERT"

class EmergencyType(str, Enum):
    AMBULANCE = "ambulance"
    FIRE      = "fire"
    VIP       = "vip"
    LOCKDOWN  = "lockdown"
    CLEAR     = "clear"


# ──────────────────────────────────────────────────────────
# IoT SENSOR
# ──────────────────────────────────────────────────────────

class SensorReading(BaseModel):
    """Raw reading from an IoT sensor node."""
    sensor_id:      str
    zone_id:        str
    timestamp:      datetime
    vehicle_count:  int   = Field(ge=0, description="Vehicles counted in last cycle")
    avg_speed_ms:   float = Field(ge=0, description="Average speed m/s")
    occupancy_pct:  float = Field(ge=0, le=100, description="Lane occupancy 0-100%")
    wait_time_s:    float = Field(ge=0, description="Average waiting time seconds")
    weather:        str   = "clear"
    # Emissions (from SUMO-style vehicle telemetry)
    co2_mgs:        float = 0.0
    nox_mgs:        float = 0.0
    fuel_mls:       float = 0.0
    noise_db:       float = 0.0


class SensorReadingResponse(BaseModel):
    status:    str
    zone_id:   str
    sensor_id: str
    processed: bool


# ──────────────────────────────────────────────────────────
# ZONE
# ──────────────────────────────────────────────────────────

class ZoneSnapshot(BaseModel):
    zone_id:       str
    name:          str
    congestion:    float
    vehicles:      int
    speed_ms:      float
    wait_time_s:   float
    status:        ZoneStatus
    incident_count: int = 0
    updated_at:    datetime

class ZoneListResponse(BaseModel):
    zones:     List[ZoneSnapshot]
    total:     int
    timestamp: datetime


# ──────────────────────────────────────────────────────────
# SIGNAL
# ──────────────────────────────────────────────────────────

class SignalState(BaseModel):
    signal_id:      str
    intersection:   str
    zone_id:        str
    phase:          SignalPhase
    elapsed_s:      float
    green_s:        int
    yellow_s:       int
    red_s:          int
    adaptive:       bool
    next_change_s:  float
    cycle_count:    int = 0

class SignalUpdateRequest(BaseModel):
    signal_id: str
    green_s:   int = Field(ge=10, le=120)
    reason:    Optional[str] = None

class SignalBulkUpdate(BaseModel):
    updates: List[SignalUpdateRequest]

class SignalOptimizationResult(BaseModel):
    signal_id:         str
    intersection:      str
    current_green_s:   int
    recommended_green_s: int
    delta_s:           int
    zone_congestion:   float
    reasoning:         str


# ──────────────────────────────────────────────────────────
# TRAFFIC METRICS
# ──────────────────────────────────────────────────────────

class FlowMetrics(BaseModel):
    total_vehicles:    int
    flow_efficiency:   float
    avg_delay_min:     float
    active_incidents:  int
    adaptive_signals:  int
    timestamp:         datetime

class RouteOption(BaseModel):
    rank:         int
    name:         str
    via:          str
    eta_min:      int
    distance_km:  float
    congestion:   float
    status:       str   # OPTIMAL / ALTERNATE / AVOID
    signals_en_route: List[str] = []

class RouteResponse(BaseModel):
    origin:      str
    destination: str
    options:     List[RouteOption]
    computed_at: datetime
    llm_advice:  Optional[str] = None


# ──────────────────────────────────────────────────────────
# ALERTS
# ──────────────────────────────────────────────────────────

class Alert(BaseModel):
    alert_id:   str
    level:      AlertLevel
    alert_type: AlertType
    message:    str
    zone_id:    Optional[str] = None
    timestamp:  datetime
    resolved:   bool = False

class AlertFeed(BaseModel):
    alerts:     List[Alert]
    total:      int
    unresolved: int


# ──────────────────────────────────────────────────────────
# EMERGENCY
# ──────────────────────────────────────────────────────────

class EmergencyRequest(BaseModel):
    emergency_type: EmergencyType
    origin:         Optional[str] = None
    destination:    Optional[str] = None
    vehicle_id:     Optional[str] = None
    notes:          Optional[str] = None

class EmergencyResponse(BaseModel):
    incident_id:    str
    emergency_type: EmergencyType
    status:         str
    corridor:       List[str]
    eta_min:        int
    message:        str
    activated_at:   datetime


# ──────────────────────────────────────────────────────────
# LLM / AI CHAT
# ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str   # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message:  str
    history:  List[ChatMessage] = []
    zone_ctx: Optional[str] = None

class ChatResponse(BaseModel):
    reply:      str
    intent:     str
    actions:    List[str] = []
    latency_ms: int
    timestamp:  datetime
    used_llm:   bool = False

class LLMPrediction(BaseModel):
    zone_id:           str
    zone_name:         str
    current_congestion: float
    predicted_congestion: float
    horizon_min:       int
    confidence:        float
    recommendation:    str
    timestamp:         datetime


# ──────────────────────────────────────────────────────────
# ANALYTICS
# ──────────────────────────────────────────────────────────

class HourlyBucket(BaseModel):
    hour:      int
    vehicles:  int
    avg_speed: float
    incidents: int

class DailySummary(BaseModel):
    date:              str
    total_vehicles:    int
    peak_hour:         int
    avg_efficiency:    float
    total_incidents:   int
    fuel_saved_l:      float
    co2_reduced_kg:    float
    hourly:            List[HourlyBucket]

class VehicleTelemetry(BaseModel):
    """SUMO-style per-vehicle telemetry (Image 2)."""
    vehicle_id:    str
    lane_id:       str
    position_m:    float
    speed_ms:      float
    lat_offset_m:  float = 0.0
    accel_ms2:     float = 0.0
    angle_deg:     float = 0.0
    wait_time_s:   float = 0.0
    time_loss_s:   float = 0.0
    co2_mgs:       float = 0.0
    co_mgs:        float = 0.0
    hc_mgs:        float = 0.0
    nox_mgs:       float = 0.0
    pmx_mgs:       float = 0.0
    fuel_mls:      float = 0.0
    noise_db:      float = 0.0
    lc_state_r:    str = "unknown"
    lc_state_l:    str = "unknown"


# ──────────────────────────────────────────────────────────
# WEBSOCKET
# ──────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type:    str   # state_update | alert | emergency | ping
    payload: Dict[str, Any] = {}
