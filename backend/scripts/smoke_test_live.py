"""Exercise the live PostgreSQL-backed API using disposable records, then remove them."""

from datetime import UTC, datetime
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.security import hash_login_key
from app.main import app
from app.models import (
    Alert,
    AuditLog,
    ComponentHealthLog,
    Device,
    DeviceComponent,
    DeviceCredential,
    DeviceTelemetry,
    LoginFailure,
    MonitoringSession,
    Patient,
    Reading,
    User,
)


def run_smoke_flow() -> None:
    suffix = uuid4().hex[:12].upper()
    patient_id = device_id = session_id = nurse2_id = None
    alert_ids: list[int] = []
    test_source_hash = hash_login_key("source:testclient")

    with SessionLocal() as db:
        db.execute(delete(LoginFailure).where(LoginFailure.source_hash == test_source_hash))
        db.commit()

    try:
        if not settings.bootstrap_admin_password:
            raise RuntimeError("Set BOOTSTRAP_ADMIN_PASSWORD in backend/.env before running the smoke flow")
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                data={"username": settings.bootstrap_admin_username, "password": settings.bootstrap_admin_password},
            )
            assert login.status_code == 200, login.text
            staff_token = login.json()["access_token"]
            staff_headers = {"Authorization": f"Bearer {staff_token}"}
            assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 200
            assert client.get("/api/v1/admin/overview").status_code == 401

            for _ in range(settings.login_identifier_max_attempts):
                denied = client.post("/api/v1/auth/login", data={"username": f"unknown-{suffix}", "password": "invalid"})
                assert denied.status_code == 401, denied.text
            throttled_login = client.post(
                "/api/v1/auth/login", data={"username": f"unknown-{suffix}", "password": "invalid"}
            )
            assert throttled_login.status_code == 429, throttled_login.text

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
            old_device_headers = {"Authorization": f"Bearer {device_secret}"}
            rotated_secret = client.post(f"/api/v1/devices/{device_id}/rotate-secret", headers=staff_headers)
            assert rotated_secret.status_code == 200, rotated_secret.text
            device_secret = rotated_secret.json()["device_secret"]
            assert client.post(
                "/api/v1/devices/sync",
                headers=old_device_headers,
                json={"device_code": f"SMK-{suffix}"},
            ).status_code == 401

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
                    },
                    {
                        "event_id": str(uuid4()),
                        "measured_at": measured_at,
                        "heart_rate_bpm": 40,
                        "spo2_percent": 50,
                        "temperature_c": 30.0,
                        "quality": "poor",
                    },
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
            poor_reading_id = first_sync.json()["readings"][1]["reading_id"]

            alerts_response = client.get("/api/v1/alerts", headers=staff_headers, params={"patient_id": patient_id})
            assert alerts_response.status_code == 200, alerts_response.text
            poor_alerts = [alert for alert in alerts_response.json() if alert["reading_id"] == poor_reading_id]
            assert len(poor_alerts) == 1 and poor_alerts[0]["alert_type"] == "device_error", poor_alerts

            rate_limited = client.post(
                "/api/v1/devices/sync",
                headers=device_headers,
                json={"device_code": f"SMK-{suffix}", "readings": [{
                    "event_id": str(uuid4()), "measured_at": measured_at, "heart_rate_bpm": 100, "quality": "ok"
                }]},
            )
            assert rate_limited.status_code == 429, rate_limited.text

            malformed_clock = client.post(
                "/api/v1/devices/sync",
                headers=device_headers,
                json={"device_code": f"SMK-{suffix}", "readings": [{
                    "event_id": str(uuid4()), "measured_at": "2026-01-01T00:00:00", "heart_rate_bpm": 100
                }]},
            )
            assert malformed_clock.status_code == 422, malformed_clock.text

            sleep(settings.device_sync_min_interval_seconds + 0.1)
            future_clock = client.post(
                "/api/v1/devices/sync",
                headers=device_headers,
                json={"device_code": f"SMK-{suffix}", "readings": [{
                    "event_id": str(uuid4()), "measured_at": "2099-01-01T00:00:00Z", "heart_rate_bpm": 100
                }]},
            )
            assert future_clock.status_code == 200 and future_clock.json()["readings"][0]["status"] == "rejected", future_clock.text

            device_status_change = client.patch(
                f"/api/v1/devices/{device_id}", headers=staff_headers, json={"status": "maintenance"}
            )
            assert device_status_change.status_code == 409, device_status_change.text

            sleep(settings.device_sync_min_interval_seconds + 0.1)
            retry_sync = client.post(
                "/api/v1/devices/sync",
                headers=device_headers,
                json={"device_code": f"SMK-{suffix}", "readings": [sync_payload["readings"][0]]},
            )
            assert retry_sync.status_code == 200, retry_sync.text
            assert retry_sync.json()["readings"][0]["status"] == "duplicate", retry_sync.text

            history = client.get(f"/api/v1/patients/{patient_id}/readings", headers=staff_headers)
            assert history.status_code == 200, history.text
            assert history.json()["data_status"] == "fresh", history.text
            assert len(history.json()["readings"]) == 2, history.text
            assert history.json()["last_device_sync_at"] is not None, history.text

            patient_page = client.get("/api/v1/patients", headers=staff_headers, params={"limit": 1, "offset": 0})
            assert patient_page.status_code == 200 and patient_page.headers.get("X-Total-Count") is not None

            health = client.get("/api/v1/admin/device-health", headers=staff_headers)
            assert health.status_code == 200, health.text
            smoke_health = next(item for item in health.json() if item["device_id"] == device_id)
            rtc = next(item for item in smoke_health["components"] if item["component_type"] == "RTC")
            assert rtc["status"] == "ok" and rtc["checked_at"] is not None, smoke_health

            nurse_password = f"Nurse-{uuid4().hex}-Aa1!"
            # Create a second nurse with a retained local variable for permission checks.
            nurse_payload = {
                "username": f"smoke2_{suffix.lower()}",
                "email": f"smoke2-{suffix.lower()}@example.com",
                "password": nurse_password,
                "role": "nurse",
            }
            nurse2_response = client.post("/api/v1/auth/users", headers=staff_headers, json=nurse_payload)
            assert nurse2_response.status_code == 201, nurse2_response.text
            nurse2_id = nurse2_response.json()["id"]
            nurse2_login = client.post("/api/v1/auth/login", data={"username": nurse_payload["username"], "password": nurse_password})
            assert nurse2_login.status_code == 200, nurse2_login.text
            nurse_headers = {"Authorization": f"Bearer {nurse2_login.json()['access_token']}"}
            assert client.get("/api/v1/admin/overview", headers=nurse_headers).status_code == 403

            alerts = client.get(
                "/api/v1/alerts",
                headers=staff_headers,
                params={"patient_id": patient_id},
            )
            assert alerts.status_code == 200, alerts.text
            assert len(alerts.json()) >= 3, alerts.text
            alert_ids.extend(alert["id"] for alert in alerts.json())

            stopped = client.post(f"/api/v1/sessions/{session_id}/stop", headers=staff_headers)
            assert stopped.status_code == 200, stopped.text

            def race_start_session():
                with TestClient(app) as race_client:
                    return race_client.post(
                        "/api/v1/sessions",
                        headers=staff_headers,
                        json={"patient_id": patient_id, "device_id": device_id},
                    )

            def race_change_device_status():
                with TestClient(app) as race_client:
                    return race_client.patch(
                        f"/api/v1/devices/{device_id}",
                        headers=staff_headers,
                        json={"status": "maintenance"},
                    )

            with ThreadPoolExecutor(max_workers=2) as workers:
                start_future = workers.submit(race_start_session)
                status_future = workers.submit(race_change_device_status)
                concurrent_start = start_future.result()
                concurrent_status = status_future.result()
            assert (concurrent_start.status_code, concurrent_status.status_code) in ((201, 409), (409, 200)), (
                concurrent_start.status_code, concurrent_status.status_code
            )
            with SessionLocal() as db:
                current_device = db.get(Device, device_id)
                active_session = db.scalar(
                    select(MonitoringSession).where(
                        MonitoringSession.device_id == device_id,
                        MonitoringSession.status == "active",
                    )
                )
                assert (current_device.status == "active" and active_session is not None) or (
                    current_device.status == "maintenance" and active_session is None
                )

        print("API smoke flow passed: login throttling/access control, quality-aware alerts, component health, session/status race, pagination, sync retry/rate limit, and device clock validation.")
    finally:
        with SessionLocal() as db:
            if alert_ids:
                db.execute(delete(AuditLog).where(AuditLog.resource_type == "alert", AuditLog.resource_id.in_(alert_ids)))
            if patient_id is not None:
                test_session_ids = list(db.scalars(
                    select(MonitoringSession.id).where(MonitoringSession.patient_id == patient_id)
                ).all())
                if test_session_ids:
                    db.execute(delete(Alert).where(Alert.session_id.in_(test_session_ids)))
                    db.execute(delete(Reading).where(Reading.session_id.in_(test_session_ids)))
                    db.execute(delete(AuditLog).where(
                        AuditLog.resource_type == "session", AuditLog.resource_id.in_(test_session_ids)
                    ))
                    db.execute(delete(MonitoringSession).where(MonitoringSession.id.in_(test_session_ids)))
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
            if nurse2_id is not None:
                db.execute(delete(AuditLog).where(AuditLog.user_id == nurse2_id))
                db.execute(delete(AuditLog).where(AuditLog.resource_id == nurse2_id, AuditLog.resource_type == "user"))
                db.execute(delete(User).where(User.id == nurse2_id))
            db.execute(delete(LoginFailure).where(LoginFailure.source_hash == test_source_hash))
            db.commit()


if __name__ == "__main__":
    run_smoke_flow()
