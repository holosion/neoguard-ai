from sqlalchemy.orm import Session

from app.models import Alert, Reading, Threshold


DEFAULT_THRESHOLDS = {
    "temp_low": 36.5,
    "temp_moderate_low": 36.0,
    "spo2_low": 90,
    "hr_low": 100,
    "hr_high": 160,
}


def active_thresholds(db: Session) -> dict[str, float]:
    rows = db.query(Threshold).filter(Threshold.is_active.is_(True)).all()
    result = dict(DEFAULT_THRESHOLDS)
    result.update({row.parameter: float(row.value) for row in rows})
    return result


def create_threshold_alerts(db: Session, reading: Reading, thresholds: dict[str, float]) -> None:
    rules: list[tuple[str, float | int | None, str, str]] = []
    temp = float(reading.temperature_c) if reading.temperature_c is not None else None
    if temp is not None:
        if temp < thresholds.get("temp_severe_low", 32.0):
            rules.append(("temperature_c", temp, "critical", "Temperature below the configured severe hypothermia threshold."))
        elif temp < thresholds.get("temp_moderate_low", 36.0):
            rules.append(("temperature_c", temp, "high", "Temperature below the configured moderate hypothermia threshold."))
        elif temp < thresholds.get("temp_low", 36.5):
            rules.append(("temperature_c", temp, "medium", "Temperature below the configured hypothermia threshold."))
    if reading.spo2_percent is not None and reading.spo2_percent < thresholds.get("spo2_low", 90):
        rules.append(("spo2_percent", reading.spo2_percent, "high", "SpO2 below the configured threshold."))
    if reading.heart_rate_bpm is not None:
        if reading.heart_rate_bpm < thresholds.get("hr_low", 100):
            rules.append(("heart_rate_bpm", reading.heart_rate_bpm, "medium", "Heart rate below the configured threshold."))
        elif reading.heart_rate_bpm > thresholds.get("hr_high", 160):
            rules.append(("heart_rate_bpm", reading.heart_rate_bpm, "medium", "Heart rate above the configured threshold."))

    for parameter, value, severity, message in rules:
        db.add(
            Alert(
                session_id=reading.session_id,
                reading_id=reading.id,
                alert_type="local_threshold",
                parameter=parameter,
                severity=severity,
                message=message,
                metadata_json={"observed_value": value, "thresholds": thresholds},
            )
        )
