"""Run against a fresh dedicated database via NEOGUARD_TEST_DATABASE_URL.

Each test creates a separate schema and drops only that schema. Never reuses the
public schema or an existing user's records. This exercises PostgreSQL locks,
constraints, API sync, inference persistence and staging transactions together.
"""
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_authenticated_device
from app.core.config import settings
from app.main import app
from app.models import Base, Device, Patient, MonitoringSession, Reading, Alert, RiskScore, ModelRegistry, User, DatasetImportRow
from app.services.risk import score_session
from app.services.risk_features import extract_features
from app.services.risk_model import load_model, predict
from scripts.import_training_archives import import_archives

URL = os.environ.get("NEOGUARD_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Set NEOGUARD_TEST_DATABASE_URL to run isolated PostgreSQL integration tests")


@pytest.fixture
def integration(monkeypatch):
    schema = "test_" + uuid4().hex
    engine = create_engine(URL, connect_args={"options": f"-csearch_path={schema}"})
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "device_sync_min_interval_seconds", 0)
    now = datetime.now(UTC)
    with Session(engine, expire_on_commit=False) as db:
        user = User(username="test", email="test@example.org", hashed_password="unused", role="admin")
        device = Device(device_code="TEST-DEVICE", status="active")
        p1, p2 = Patient(patient_code="TEST-P1"), Patient(patient_code="TEST-P2")
        db.add_all([user, device, p1, p2])
        db.flush()
        old = MonitoringSession(patient_id=p1.id, device_id=device.id, status="stopped", started_at=now-timedelta(hours=2), ended_at=now-timedelta(hours=1))
        current = MonitoringSession(patient_id=p2.id, device_id=device.id, status="active", started_at=now-timedelta(minutes=30))
        db.add_all([old, current])
        db.commit()
        ids = {"old": old.id, "current": current.id, "device": device.id, "p1": p1.id, "p2": p2.id, "user": user.id}

    def database():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    def staff():
        with Session(engine) as db:
            return db.get(User, ids["user"])

    def authenticated_device():
        with Session(engine) as db:
            return db.get(Device, ids["device"])

    app.dependency_overrides.update({get_db: database, get_current_user: staff, get_authenticated_device: authenticated_device})
    try:
        with TestClient(app) as client:
            yield client, engine, ids, now
    finally:
        app.dependency_overrides.clear()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def event(session, when, temp=37, spo2=98, quality="ok"):
    return {"session_id": session, "event_id": str(uuid4()), "measured_at": when.isoformat(),
            "heart_rate_bpm": 140, "spo2_percent": spo2, "temperature_c": temp, "quality": quality}


def sync(client, rows):
    result = client.post("/api/v1/devices/sync", json={"device_code": "TEST-DEVICE", "readings": rows})
    assert result.status_code == 200, result.text
    return result.json()["readings"]


def test_offline_replay_keeps_original_patient_and_checks_session_bounds(integration):
    client, engine, ids, now = integration
    valid = event(ids["old"], now-timedelta(minutes=90), temp=35.9)
    invalid = event(ids["old"], now)
    before = event(ids["current"], now-timedelta(hours=3))
    result = sync(client, [valid, invalid, before])
    assert [r["status"] for r in result] == ["accepted", "rejected", "rejected"]
    with Session(engine) as db:
        saved = db.scalar(select(Reading))
        assert saved.session_id == ids["old"]
        alert = db.scalar(select(Alert))
        assert alert.metadata_json["historical"] is True
        assert db.scalar(select(func.count(RiskScore.id))) == 0
    assert sync(client, [valid])[0]["status"] == "duplicate"
    changed = {**valid, "temperature_c": 36.1}
    assert sync(client, [changed])[0]["status"] == "rejected"


def test_sorted_replay_episodes_recovery_escalation_and_duplicate_events(integration):
    client, engine, ids, now = integration
    start = now-timedelta(minutes=5)
    rows = [event(ids["current"], start+timedelta(seconds=i*5), temp=t)
            for i, t in enumerate([36.4, 36.4, 36.4, 35.8, 35.8, 37, 36.4])]
    result = sync(client, list(reversed(rows)))
    assert all(r["status"] == "accepted" for r in result)
    with Session(engine) as db:
        assert db.scalar(select(func.count(Alert.id))) == 3
    assert all(r["status"] == "duplicate" for r in sync(client, rows))
    extra = event(ids["current"], now)
    assert [r["status"] for r in sync(client, [extra, extra])] == ["accepted", "duplicate"]


def test_fresh_window_scores_once_and_bad_quality_hides_previous_score(integration):
    client, engine, ids, now = integration
    start = now-timedelta(seconds=125)
    rows = [event(ids["current"], start+timedelta(seconds=i*5), temp=round(37-i*0.01,2)) for i in range(25)]
    sync(client, rows)
    response = client.get(f'/api/v1/patients/{ids["p2"]}/risk-score')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "prototype" and result["validation_scope"] == "synthetic_only"
    expected = predict(load_model(settings.ai_model_path), extract_features(rows))["score"]
    assert result["score"] == pytest.approx(expected, abs=0.00001)
    with Session(engine) as db:
        score_session(db, ids["current"])
        db.commit()
        assert db.scalar(select(func.count(RiskScore.id))) == 1
        assert db.scalar(select(ModelRegistry)).status == "candidate"
    bad = event(ids["current"], now, quality="motion_artifact")
    sync(client, [bad])
    response = client.get(f'/api/v1/patients/{ids["p2"]}/risk-score').json()
    assert response["status"] == "insufficient_data" and response["score"] is None


def test_model_failure_never_rolls_back_readings(integration, monkeypatch):
    client, engine, ids, now = integration
    import app.api.v1.endpoints.devices as endpoint
    def fail(*args):
        raise RuntimeError("Injected model failure")
    monkeypatch.setattr(endpoint, "score_session", fail)
    assert sync(client, [event(ids["current"], now)])[0]["status"] == "accepted"
    with Session(engine) as db:
        assert db.scalar(select(func.count(Reading.id))) == 1


def test_database_rejects_cross_device_session_reading(integration):
    client, engine, ids, now = integration
    with Session(engine) as db:
        other = Device(device_code="OTHER", status="active")
        db.add(other)
        db.flush()
        db.add(Reading(session_id=ids["current"], device_id=other.id, device_event_id=uuid4(), measured_at=now, heart_rate_bpm=140))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_archive_import_is_separate_idempotent_and_deidentified(integration):
    client, engine, ids, now = integration
    with Session(engine) as db:
        report = import_archives(db)
        db.commit()
        assert [r["status"] for r in report] == ["review", "review"]
        assert db.scalar(select(func.count(DatasetImportRow.id))) == 3200
        assert db.scalar(select(func.count(Patient.id))) == 2
        assert db.scalar(select(func.count(Reading.id))) == 0
        again = import_archives(db)
        assert all(r["status"] == "duplicate" for r in again)
        assert all("name" not in r.raw_payload and "code" not in r.raw_payload for r in db.scalars(select(DatasetImportRow)).all())
