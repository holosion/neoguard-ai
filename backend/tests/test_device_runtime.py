from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_authenticated_device, get_db
from app.api.v1.endpoints import devices
from app.main import app
from app.services.alerts import ThresholdSet


def test_runtime_requires_a_device_credential():
    with TestClient(app) as client:
        assert client.get("/api/v1/devices/runtime").status_code == 401


def test_runtime_is_device_scoped_and_uses_active_thresholds(monkeypatch):
    session = SimpleNamespace(id=42, started_at=datetime(2026, 10, 20, 6, tzinfo=UTC))

    class Database:
        def scalar(self, statement):
            params = statement.compile().params
            assert params["device_id_1"] == 77
            assert params["status_1"] == "active"
            return session

    configured = {"hr_low": 105, "hr_high": 165, "temp_low": 36.6, "spo2_low": 91}
    monkeypatch.setattr(devices, "active_thresholds", lambda _: ThresholdSet(configured, {}))
    app.dependency_overrides[get_db] = lambda: Database()
    app.dependency_overrides[get_authenticated_device] = lambda: SimpleNamespace(id=77, device_code="TEST-DEVICE")
    try:
        with TestClient(app) as client:
            result = client.get("/api/v1/devices/runtime")
            assert result.status_code == 200
            data = result.json()
            assert data["session_id"] == 42
            assert data["session_started_unix"] == int(session.started_at.timestamp())
            assert data["thresholds"] == configured
            assert data["server_time_unix"] > 0
            session = None
            data = client.get("/api/v1/devices/runtime").json()
            assert data["session_id"] is None and data["session_started_unix"] is None
    finally:
        app.dependency_overrides.clear()
