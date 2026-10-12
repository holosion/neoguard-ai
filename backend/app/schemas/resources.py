from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.common import DeviceStatus, ORMModel, Role, SessionStatus


class UserPublic(ORMModel):
    id: int
    username: str
    email: str
    role: Role
    is_active: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "nurse", "clinician"]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PatientCreate(BaseModel):
    patient_code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    sex: Literal["M", "F", "U"] | None = None
    birth_date: date | None = None
    gestational_age_weeks: int | None = Field(default=None, ge=20, le=45)
    birth_weight_kg: float | None = Field(default=None, ge=0.3, le=8)


class PatientUpdate(BaseModel):
    sex: Literal["M", "F", "U"] | None = None
    birth_date: date | None = None
    gestational_age_weeks: int | None = Field(default=None, ge=20, le=45)
    birth_weight_kg: float | None = Field(default=None, ge=0.3, le=8)


class PatientPublic(ORMModel):
    id: int
    patient_code: str
    sex: str | None
    birth_date: date | None
    gestational_age_weeks: int | None
    birth_weight_kg: float | None
    created_at: datetime


class RiskProfileUpsert(BaseModel):
    low_birth_weight: bool | None = None
    prematurity: bool | None = None
    home_birth: bool | None = None
    delayed_breastfeeding: bool | None = None
    skin_to_skin: bool | None = None
    socioeconomic_status: Literal["poorest", "poor", "middle", "rich", "richest"] | None = None
    other_factors: dict | None = None


class RiskProfilePublic(ORMModel):
    id: int
    patient_id: int
    low_birth_weight: bool | None
    prematurity: bool | None
    home_birth: bool | None
    delayed_breastfeeding: bool | None
    skin_to_skin: bool | None
    socioeconomic_status: str | None
    other_factors: dict | None
    updated_by_user_id: int | None


class ComponentCreate(BaseModel):
    component_type: str = Field(min_length=2, max_length=50)
    pin_or_address: str | None = Field(default=None, max_length=50)
    is_critical: bool = True


class DeviceCreate(BaseModel):
    device_code: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = Field(default=None, max_length=80)
    status: DeviceStatus = "inactive"
    hardware_version: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=120)
    components: list[ComponentCreate] = Field(default_factory=list)


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    status: DeviceStatus | None = None
    firmware_version: str | None = Field(default=None, max_length=30)
    hardware_version: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=120)


class DevicePublic(ORMModel):
    id: int
    device_code: str
    name: str | None
    status: str
    firmware_version: str | None
    hardware_version: str | None
    location: str | None
    last_seen_online: datetime | None
    last_sync_received_at: datetime | None


class DeviceCreated(DevicePublic):
    device_secret: str


class DeviceSecretOut(BaseModel):
    device_code: str
    device_secret: str
    created_at: datetime


class SessionCreate(BaseModel):
    patient_id: int = Field(gt=0)
    device_id: int = Field(gt=0)


class SessionPublic(ORMModel):
    id: int
    patient_id: int
    device_id: int
    started_by_user_id: int | None
    started_at: datetime
    ended_at: datetime | None
    status: SessionStatus


class ReadingIn(BaseModel):
    session_id: int = Field(gt=0, description="Original session ID retained with the event in the device offline queue")
    event_id: UUID
    measured_at: datetime
    heart_rate_bpm: int | None = Field(default=None, ge=40, le=220)
    spo2_percent: int | None = Field(default=None, ge=50, le=100)
    temperature_c: float | None = Field(default=None, ge=30, le=42)
    quality: Literal["ok", "poor", "motion_artifact", "sensor_error"] = "ok"

    @model_validator(mode="after")
    def require_a_measurement(self):
        if all(value is None for value in (self.heart_rate_bpm, self.spo2_percent, self.temperature_c)):
            raise ValueError("At least one vital sign is required")
        if self.measured_at.tzinfo is None:
            raise ValueError("measured_at must include a timezone")
        return self


class TelemetryIn(BaseModel):
    reported_at: datetime
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    wifi_rssi_dbm: int | None = Field(default=None, ge=-127, le=0)
    uptime_seconds: int | None = Field(default=None, ge=0)

    @field_validator("reported_at")
    @classmethod
    def timezone_required(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("reported_at must include a timezone")
        return value


class ComponentCheckIn(BaseModel):
    component_type: str = Field(min_length=2, max_length=50)
    checked_at: datetime
    status: Literal["ok", "error", "timeout", "not_detected", "drift_detected"]
    error_code: str | None = Field(default=None, max_length=50)
    details: dict | None = None

    @field_validator("checked_at")
    @classmethod
    def timezone_required(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("checked_at must include a timezone")
        return value


class DeviceSyncIn(BaseModel):
    device_code: str = Field(min_length=3, max_length=30)
    firmware_version: str | None = Field(default=None, max_length=30)
    readings: list[ReadingIn] = Field(default_factory=list, max_length=500)
    telemetry: TelemetryIn | None = None
    component_checks: list[ComponentCheckIn] = Field(default_factory=list, max_length=100)


class SyncItemResult(BaseModel):
    event_id: UUID
    status: Literal["accepted", "duplicate", "rejected"]
    reading_id: int | None = None
    reason: str | None = None


class DeviceSyncOut(BaseModel):
    device_code: str
    received_at: datetime
    readings: list[SyncItemResult]


class ReadingPublic(ORMModel):
    id: int
    session_id: int
    device_event_id: UUID
    measured_at: datetime
    received_at: datetime
    heart_rate_bpm: int | None
    spo2_percent: int | None
    temperature_c: float | None
    quality: str


class ReadingHistory(BaseModel):
    patient_code: str
    readings: list[ReadingPublic]
    data_status: Literal["empty", "fresh", "stale"]
    last_measured_at: datetime | None
    last_synced_at: datetime | None
    last_device_sync_at: datetime | None = None
    stale_after_seconds: int


class AlertPublic(ORMModel):
    id: int
    session_id: int
    reading_id: int | None
    alert_type: str
    parameter: str | None
    severity: str
    message: str
    metadata_json: dict | None
    acknowledged_at: datetime | None
    acknowledged_by_user_id: int | None
    created_at: datetime


class PatientListItem(BaseModel):
    patient: PatientPublic
    active_session: SessionPublic | None
    latest_reading: ReadingPublic | None
    data_status: Literal["unmonitored", "empty", "fresh", "stale"]
    risk: dict | None = None
