from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Reading, Threshold
from app.core.config import settings


DEFAULT_THRESHOLDS = {
    "temp_low": 36.5,
    "temp_moderate_low": 36.0,
    "temp_severe_low": 32.0,
    "spo2_low": 90,
    "hr_low": 100,
    "hr_high": 160,
}


@dataclass(frozen=True)
class ThresholdSet:
    values: dict[str, float]
    provenance: dict[str, dict]


def active_thresholds(db: Session) -> ThresholdSet:
    rows = db.query(Threshold).filter(Threshold.is_active.is_(True)).all()
    result = dict(DEFAULT_THRESHOLDS)
    provenance = {
        parameter: {
            "value": value,
            "unit": "°C" if parameter.startswith("temp_") else ("%" if parameter == "spo2_low" else "bpm"),
            "version": "code-default",
            "source": "Project provisional default; clinical review required",
        }
        for parameter, value in DEFAULT_THRESHOLDS.items()
    }
    for row in rows:
        result[row.parameter] = float(row.value)
        provenance[row.parameter] = {
            "threshold_id": row.id,
            "value": float(row.value),
            "unit": row.unit,
            "version": row.version,
            "source": row.source,
        }
    return ThresholdSet(values=result, provenance=provenance)


def rules_for_reading(reading: Reading, thresholds: ThresholdSet):
    if reading.quality != "ok":
        return [("quality", reading.quality, "medium", f"Reading quality is '{reading.quality}'; vital thresholds were not evaluated.")]
    values = thresholds.values
    rules: list[tuple[str, float | int | None, str, str]] = []
    temp = float(reading.temperature_c) if reading.temperature_c is not None else None
    if temp is not None:
        if temp < values.get("temp_severe_low", 32.0):
            rules.append(("temperature_c", temp, "critical", "Temperature below the configured severe hypothermia threshold."))
        elif temp < values.get("temp_moderate_low", 36.0):
            rules.append(("temperature_c", temp, "high", "Temperature below the configured moderate hypothermia threshold."))
        elif temp < values.get("temp_low", 36.5):
            rules.append(("temperature_c", temp, "medium", "Temperature below the configured hypothermia threshold."))
    if reading.spo2_percent is not None and reading.spo2_percent < values.get("spo2_low", 90):
        rules.append(("spo2_percent", reading.spo2_percent, "high", "SpO2 below the configured threshold."))
    if reading.heart_rate_bpm is not None:
        if reading.heart_rate_bpm < values.get("hr_low", 100):
            rules.append(("heart_rate_bpm", reading.heart_rate_bpm, "medium", "Heart rate below the configured threshold."))
        elif reading.heart_rate_bpm > values.get("hr_high", 160):
            rules.append(("heart_rate_bpm", reading.heart_rate_bpm, "medium", "Heart rate above the configured threshold."))

    return rules


def create_threshold_alerts(db: Session, reading: Reading, thresholds: ThresholdSet) -> None:
    previous = db.scalar(select(Reading).where(Reading.session_id == reading.session_id,
                         Reading.measured_at < reading.measured_at,
                         Reading.measured_at >= reading.measured_at - timedelta(seconds=15)).order_by(Reading.measured_at.desc(), Reading.id.desc()).limit(1))
    previous_rules = {(p, severity): value for p, value, severity, message in rules_for_reading(previous, thresholds)} if previous else {}
    for parameter, value, severity, message in rules_for_reading(reading, thresholds):
        # One alert per contiguous episode; recovery or escalation opens a new alert.
        if (parameter, severity) in previous_rules and (parameter != "quality" or previous_rules[(parameter, severity)] == value):
            continue
        historical = reading.measured_at < datetime.now(UTC) - timedelta(seconds=settings.reading_stale_after_seconds)
        db.add(
            Alert(
                session_id=reading.session_id,
                reading_id=reading.id,
                alert_type="device_error" if parameter == "quality" else "backend_threshold",
                parameter=parameter,
                severity=severity,
                message=message,
                metadata_json={
                    "observed_value": value,
                    "thresholds": thresholds.provenance,
                    "historical": historical,
                    "measured_at": reading.measured_at.isoformat(),
                    "origin": "backend_evaluation",
                },
            )
        )
