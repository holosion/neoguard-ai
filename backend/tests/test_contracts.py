from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.api.v1.endpoints.devices import validate_reading_session
from app.core.config import settings
from app.main import app
from app.schemas.resources import ReadingIn
from app.services.alerts import DEFAULT_THRESHOLDS, ThresholdSet, rules_for_reading


def test_session_boundaries_include_valid_historical_uploads():
    now = datetime.now(UTC)
    old = SimpleNamespace(device_id=7, started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1))
    reading = SimpleNamespace(measured_at=now - timedelta(minutes=90))
    assert validate_reading_session(reading, old, 7, now) is None
    assert validate_reading_session(reading, old, 8, now) == "Session does not belong to this device"
    reading.measured_at = now
    assert "ended" in validate_reading_session(reading, old, 7, now)
    reading.measured_at = old.started_at - timedelta(seconds=1)
    assert "predates" in validate_reading_session(reading, old, 7, now)


def test_session_id_is_required_and_naive_clock_is_rejected():
    payload = {"event_id": str(uuid4()), "measured_at": datetime.now(UTC), "heart_rate_bpm": 140}
    with pytest.raises(ValidationError):
        ReadingIn(**payload)
    payload["session_id"] = 1
    payload["measured_at"] = datetime.now()
    with pytest.raises(ValidationError):
        ReadingIn(**payload)


def test_browser_can_update_risk_profiles_and_read_pagination_headers():
    with TestClient(app) as client:
        result = client.options("/api/v1/patients/1/risk-profile", headers={"Origin": settings.cors_origins[0],
                                "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "Authorization,Content-Type"})
        assert result.status_code == 200
        result = client.get("/health", headers={"Origin": settings.cors_origins[0]})
        assert "X-Total-Count" in result.headers["access-control-expose-headers"]


def test_sensor_quality_and_temperature_escalation():
    thresholds = ThresholdSet(DEFAULT_THRESHOLDS, {})
    row = SimpleNamespace(quality="ok", temperature_c=36.4, spo2_percent=98, heart_rate_bpm=140)
    assert rules_for_reading(row, thresholds)[0][2] == "medium"
    row.temperature_c = 35.9
    assert rules_for_reading(row, thresholds)[0][2] == "high"
    row.quality = "sensor_error"
    assert [r[0] for r in rules_for_reading(row, thresholds)] == ["quality"]
