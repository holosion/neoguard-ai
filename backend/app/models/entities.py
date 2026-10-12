from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="nurse")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("role IN ('admin', 'nurse', 'clinician')", name="ck_users_role"),)


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    sex: Mapped[str | None] = mapped_column(String(1))
    birth_date: Mapped[date | None] = mapped_column(Date)
    gestational_age_weeks: Mapped[int | None] = mapped_column(SmallInteger)
    birth_weight_kg: Mapped[float | None] = mapped_column(Numeric(4, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utc_now)


class RiskProfile(Base):
    __tablename__ = "risk_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), unique=True)
    low_birth_weight: Mapped[bool | None] = mapped_column(Boolean)
    prematurity: Mapped[bool | None] = mapped_column(Boolean)
    home_birth: Mapped[bool | None] = mapped_column(Boolean)
    delayed_breastfeeding: Mapped[bool | None] = mapped_column(Boolean)
    skin_to_skin: Mapped[bool | None] = mapped_column(Boolean)
    socioeconomic_status: Mapped[str | None] = mapped_column(String(20))
    other_factors: Mapped[dict | None] = mapped_column(JSON)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utc_now)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="inactive", index=True)
    firmware_version: Mapped[str | None] = mapped_column(String(30))
    hardware_version: Mapped[str | None] = mapped_column(String(30))
    location: Mapped[str | None] = mapped_column(String(120))
    last_seen_online: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utc_now)

    __table_args__ = (CheckConstraint("status IN ('inactive', 'active', 'maintenance', 'retired')", name="ck_devices_status"),)


class DeviceCredential(Base):
    __tablename__ = "device_credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), unique=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceComponent(Base):
    __tablename__ = "device_components"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    component_type: Mapped[str] = mapped_column(String(50))
    pin_or_address: Mapped[str | None] = mapped_column(String(50))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("device_id", "component_type", name="uq_device_component_type"),)


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    started_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'stopped')", name="ck_session_status"),
        CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) OR (status <> 'active' AND ended_at IS NOT NULL)",
            name="ck_session_end_time",
        ),
        Index("uq_active_session_device", "device_id", unique=True, postgresql_where=text("status = 'active'")),
        Index("uq_active_session_patient", "patient_id", unique=True, postgresql_where=text("status = 'active'")),
        UniqueConstraint("patient_id", "id", name="uq_session_patient_id"),
        UniqueConstraint("device_id", "id", name="uq_session_device_id"),
    )


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="RESTRICT"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    device_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    heart_rate_bpm: Mapped[int | None] = mapped_column(SmallInteger)
    spo2_percent: Mapped[int | None] = mapped_column(SmallInteger)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(4, 2))
    quality: Mapped[str] = mapped_column(String(30), default="ok")

    __table_args__ = (
        UniqueConstraint("device_id", "device_event_id", name="uq_reading_device_event"),
        ForeignKeyConstraint(["device_id", "session_id"], ["monitoring_sessions.device_id", "monitoring_sessions.id"],
                             name="fk_reading_device_session", ondelete="RESTRICT"),
        CheckConstraint("heart_rate_bpm IS NULL OR heart_rate_bpm BETWEEN 40 AND 220", name="ck_reading_hr"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 50 AND 100", name="ck_reading_spo2"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 30 AND 42", name="ck_reading_temp"),
        CheckConstraint("heart_rate_bpm IS NOT NULL OR spo2_percent IS NOT NULL OR temperature_c IS NOT NULL", name="ck_reading_has_measurement"),
        Index("ix_readings_session_measured", "session_id", "measured_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="RESTRICT"), index=True)
    reading_id: Mapped[int | None] = mapped_column(ForeignKey("readings.id", ondelete="SET NULL"), index=True)
    alert_type: Mapped[str] = mapped_column(String(30))
    parameter: Mapped[str | None] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("reading_id", "alert_type", "parameter", name="uq_alert_per_reading_rule"),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_alert_severity"),
        Index("ix_alerts_ack_created", "acknowledged_at", "created_at"),
    )


class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    battery_percent: Mapped[int | None] = mapped_column(SmallInteger)
    wifi_rssi_dbm: Mapped[int | None] = mapped_column(SmallInteger)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("battery_percent IS NULL OR battery_percent BETWEEN 0 AND 100", name="ck_battery_percent"),
        Index("ix_telemetry_device_reported", "device_id", "reported_at"),
    )


class DatasetImport(Base):
    """Provenance record for an offline research/training dataset import."""

    __tablename__ = "dataset_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(80), index=True)
    archive_name: Mapped[str] = mapped_column(String(255))
    member_name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(40), default="unreviewed")
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    source_reference: Mapped[str | None] = mapped_column(Text)
    rows_seen: Mapped[int] = mapped_column(Integer, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[dict | None] = mapped_column(JSONB)
    imported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dataset_key", "sha256", name="uq_dataset_import_file"),
        CheckConstraint("status IN ('received', 'review', 'imported', 'rejected')", name="ck_dataset_import_status"),
        CheckConstraint("rows_seen >= 0 AND rows_accepted >= 0 AND rows_rejected >= 0", name="ck_dataset_import_counts"),
    )


class LoginFailure(Base):
    __tablename__ = "login_failures"
    id: Mapped[int] = mapped_column(primary_key=True)
    identifier_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class DatasetImportRow(Base):
    """Staging/provenance row; never queried by live patient dashboard endpoints."""

    __tablename__ = "dataset_import_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_import_id: Mapped[int] = mapped_column(ForeignKey("dataset_imports.id", ondelete="CASCADE"), index=True)
    source_row_number: Mapped[int] = mapped_column(Integer)
    external_subject_id: Mapped[str | None] = mapped_column(String(100), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    quality_flags: Mapped[list | None] = mapped_column(JSONB)
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dataset_import_id", "source_row_number", name="uq_dataset_import_source_row"),
        CheckConstraint("source_row_number > 0", name="ck_dataset_source_row_positive"),
        CheckConstraint("validation_status IN ('pending', 'accepted', 'rejected', 'review')", name="ck_dataset_row_status"),
    )


class DatasetSubject(Base):
    """Pseudonymous research subject; deliberately separate from clinical Patient."""

    __tablename__ = "dataset_subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_import_id: Mapped[int] = mapped_column(ForeignKey("dataset_imports.id", ondelete="CASCADE"), index=True)
    external_subject_id: Mapped[str] = mapped_column(String(100))
    sex: Mapped[str | None] = mapped_column(String(1))
    gestational_age_weeks: Mapped[float | None] = mapped_column(Numeric(4, 1))
    birth_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 3))
    birth_length_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    birth_head_circumference_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    apgar_score: Mapped[float | None] = mapped_column(Numeric(3, 1))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dataset_import_id", "external_subject_id", name="uq_dataset_subject_external_id"),
        UniqueConstraint("dataset_import_id", "id", name="uq_dataset_subject_import_id"),
    )


class DatasetObservation(Base):
    """Typed day-level research data; date-only by design, not a fake device timestamp."""

    __tablename__ = "dataset_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_import_id: Mapped[int] = mapped_column(ForeignKey("dataset_imports.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("dataset_subjects.id", ondelete="CASCADE"), index=True)
    source_row_number: Mapped[int] = mapped_column(Integer)
    observed_on: Mapped[date | None] = mapped_column(Date, index=True)
    age_days: Mapped[int | None] = mapped_column(SmallInteger)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 3))
    length_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    head_circumference_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2))
    heart_rate_bpm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    respiratory_rate_bpm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    spo2_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    feeding_type: Mapped[str | None] = mapped_column(String(40))
    feeding_frequency_per_day: Mapped[int | None] = mapped_column(SmallInteger)
    urine_output_count: Mapped[int | None] = mapped_column(SmallInteger)
    stool_count: Mapped[int | None] = mapped_column(SmallInteger)
    jaundice_level_mg_dl: Mapped[float | None] = mapped_column(Numeric(5, 2))
    immunizations_done: Mapped[bool | None] = mapped_column(Boolean)
    reflexes_normal: Mapped[bool | None] = mapped_column(Boolean)
    imported_risk_label: Mapped[str | None] = mapped_column(String(80))
    quality_flags: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dataset_import_id", "source_row_number", name="uq_dataset_observation_source_row"),
        ForeignKeyConstraint(
            ["dataset_import_id", "subject_id"],
            ["dataset_subjects.dataset_import_id", "dataset_subjects.id"],
            name="fk_dataset_observation_same_import_subject",
            ondelete="CASCADE",
        ),
        Index("ix_dataset_observation_subject_date", "subject_id", "observed_on"),
    )


class ModelRegistry(Base):
    """Versioned metadata for future models; artifacts themselves stay in controlled file storage."""

    __tablename__ = "model_registry"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_key: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(40))
    task_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="candidate", index=True)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    training_dataset_import_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataset_imports.id", ondelete="SET NULL"), index=True
    )
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    validation_notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("model_key", "version", name="uq_model_key_version"),
        CheckConstraint("status IN ('candidate', 'approved', 'retired')", name="ck_model_registry_status"),
    )


class RiskScore(Base):
    """Immutable versioned inference snapshot, explicitly scoped by its model metadata."""

    __tablename__ = "risk_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    session_id: Mapped[int | None] = mapped_column(Integer, index=True)
    model_registry_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id", ondelete="RESTRICT"), index=True)
    score: Mapped[float] = mapped_column(Numeric(6, 5))
    risk_category: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(80))
    data_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feature_snapshot: Mapped[dict] = mapped_column(JSONB)
    explanation: Mapped[dict | None] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("session_id", "model_registry_id", "data_window_end", name="uq_risk_score_window_model"),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_risk_score_range"),
        CheckConstraint("risk_category IN ('low', 'moderate', 'high', 'critical')", name="ck_risk_score_category"),
        CheckConstraint(
            "data_window_start IS NULL OR data_window_end IS NULL OR data_window_start <= data_window_end",
            name="ck_risk_score_window",
        ),
        ForeignKeyConstraint(
            ["patient_id", "session_id"],
            ["monitoring_sessions.patient_id", "monitoring_sessions.id"],
            name="fk_risk_score_patient_session",
            ondelete="RESTRICT",
        ),
    )


class OutcomeLabel(Base):
    """Explicitly reviewed outcome labels, separate from model predictions and live alerts."""

    __tablename__ = "outcome_labels"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    dataset_subject_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_subjects.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(String(80), index=True)
    label_value: Mapped[dict] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(200))
    evidence_reference: Mapped[str | None] = mapped_column(Text)
    observed_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str] = mapped_column(String(20), default="unreviewed", index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "(patient_id IS NOT NULL AND dataset_subject_id IS NULL) OR "
            "(patient_id IS NULL AND dataset_subject_id IS NOT NULL)",
            name="ck_outcome_label_exactly_one_subject",
        ),
        CheckConstraint("review_status IN ('unreviewed', 'confirmed', 'rejected')", name="ck_outcome_label_review_status"),
        CheckConstraint("observed_from IS NULL OR observed_to IS NULL OR observed_from <= observed_to", name="ck_outcome_label_window"),
    )


class ComponentHealthLog(Base):
    __tablename__ = "component_health_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("device_components.id", ondelete="CASCADE"), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(30))
    error_code: Mapped[str | None] = mapped_column(String(50))
    details: Mapped[dict | None] = mapped_column(JSON)


class Threshold(Base):
    __tablename__ = "thresholds"
    id: Mapped[int] = mapped_column(primary_key=True)
    parameter: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[float] = mapped_column(Numeric(8, 2))
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("parameter", "version", name="uq_threshold_parameter_version"),
        Index("uq_active_threshold_parameter", "parameter", unique=True, postgresql_where=text("is_active = true")),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
