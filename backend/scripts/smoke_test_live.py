"""Exercise the live PostgreSQL-backed API using disposable records, then remove them."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import (
    Alert,
    AuditLog,
    ComponentHealthLog,
    Device,
    DeviceComponent,
    DeviceCredential,
    DeviceTelemetry,
    MonitoringSession,
    Patient,
    Reading,
)


def run_smoke_flow() -> None:
    suffix = uuid4().hex[:12].upper()
    patient_id = device_id = session_id = None
    reading_ids: list[int] = []
    alert_ids: list[int] = []

    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                data={"username": "admin", "password": "okuja"},
            )
            assert login.status_code == 200, login.text
            staff_token = login.json()["access_token"]
            staff_headers = {"Authorization": f"Bearer {staff_token}"}
            assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 200

            patient_response = client.post(
                "/api/v1/patients",
                headers=staff_headers,
                json={"patient_code": f"SMK-{suffix}", "sex": "U"},
            )
            assert patient_response.status_code == 201, patient_response.text
            patient_id = patient_response.json()["id"]

            device_response = client.post(
                "/api/v1/devices",
                headers=staff_headers,
                json={
                    "device_code": f"SMK-{suffix}",
                    "status": "active",
                    "components": [
                        {"component_type": "RTC"},
                        {"component_type": "LCD"},
                        {"component_type": "MAX30102"},
                    ],
                },
            )
            assert device_response.status_code == 201, device_response.text
            device_id = device_response.json()["id"]
            device_secret = device_response.json()["device_secret"]

            session_response = client.post(
                "/api/v1/sessions",
                headers=staff_headers,
                json={"patient_id": patient_id, "device_id": device_id},
            )
            assert session_response.status_code == 201, session_response.text
            session_id = session_response.json()["id"]

            event_id = str(uuid4())
            measured_at = datetime.now(UTC).isoformat()
            sync_payload = {
                "device_code": f"SMK-{suffix}",
                "firmware_version": "smoke-test",
                "readings": [
                    {
                        "event_id": event_id,
                        "measured_at": measured_at,
                        "heart_rate_bpm": 98,
                        "spo2_percent": 88,
                        "temperature_c": 35.9,
                        "quality": "ok",
                    }
                ],
                "telemetry": {
                    "reported_at": measured_at,
                    "battery_percent": 90,
                    "wifi_rssi_dbm": -65,
                    "uptime_seconds": 120,
                },
                "component_checks": [
                    {"component_type": "RTC", "checked_at": measured_at, "status": "ok"},
                    {"component_type": "LCD", "checked_at": measured_at, "status": "ok"},
                ],
            }
            device_headers = {"Authorization": f"Bearer {device_secret}"}
            first_sync = client.post("/api/v1/devices/sync", headers=device_headers, json=sync_payload)
            assert first_sync.status_code == 200, first_sync.text
            assert first_sync.json()["readings"][0]["status"] == "accepted", first_sync.text
            reading_ids.append(first_sync.json()["readings"][0]["reading_id"])

            retry_sync = client.post("/api/v1/devices/sync", headers=device_headers, json=sync_payload)
            assert retry_sync.status_code == 200, retry_sync.text
            assert retry_sync.json()["readings"][0]["status"] == "duplicate", retry_sync.text

            history = client.get(f"/api/v1/patients/{patient_id}/readings", headers=staff_headers)
            assert history.status_code == 200, history.text
            assert history.json()["data_status"] == "fresh", history.text
            assert len(history.json()["readings"]) == 1, history.text

            alerts = client.get(
                "/api/v1/alerts",
                headers=staff_headers,
                params={"patient_id": patient_id},
            )
            assert alerts.status_code == 200, alerts.text
            assert len(alerts.json()) >= 3, alerts.text
            alert_ids.extend(alert["id"] for alert in alerts.json())

        print("API smoke flow passed: staff login, patient/device/session setup, sync, duplicate retry, readings, and alerts.")
    finally:
        with SessionLocal() as db:
            if alert_ids:
                db.execute(delete(AuditLog).where(AuditLog.resource_type == "alert", AuditLog.resource_id.in_(alert_ids)))
            if session_id is not None:
                db.execute(delete(Alert).where(Alert.session_id == session_id))
                db.execute(delete(Reading).where(Reading.session_id == session_id))
                db.execute(delete(MonitoringSession).where(MonitoringSession.id == session_id))
                db.execute(delete(AuditLog).where(AuditLog.resource_type == "session", AuditLog.resource_id == session_id))
            if device_id is not None:
                db.execute(delete(ComponentHealthLog).where(ComponentHealthLog.device_id == device_id))
                db.execute(delete(DeviceTelemetry).where(DeviceTelemetry.device_id == device_id))
                db.execute(delete(DeviceCredential).where(DeviceCredential.device_id == device_id))
                db.execute(delete(DeviceComponent).where(DeviceComponent.device_id == device_id))
                db.execute(delete(AuditLog).where(AuditLog.resource_type == "device", AuditLog.resource_id == device_id))
                db.execute(delete(Device).where(Device.id == device_id))
            if patient_id is not None:
                db.execute(delete(AuditLog).where(AuditLog.resource_type == "patient", AuditLog.resource_id == patient_id))
                db.execute(delete(Patient).where(Patient.id == patient_id))
            db.commit()


if __name__ == "__main__":
    run_smoke_flow()
