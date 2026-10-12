"""Persist experimental scores after sync, independently of the safety alert path."""
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.models import ModelRegistry, MonitoringSession, Reading, RiskScore
from app.services.risk_features import WINDOW_SECONDS, extract_features
from app.services.risk_model import load_model, predict
from app.services.alerts import active_thresholds

logger = logging.getLogger(__name__)
NOTICE = "Synthetic research prototype; not a clinically validated risk probability."


def configured_model():
    if settings.ai_mode == "disabled":
        return None, "disabled"
    try:
        return load_model(settings.ai_model_path), "ready"
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        logger.warning("AI artifact is missing or invalid; threshold alerts remain active")
        return None, "model_unavailable"


def score_session(db, session_id):
    session = db.get(MonitoringSession, session_id)
    if session is None or session.status != "active":
        return None
    model, status = configured_model()
    if model is None:
        return None
    if not thresholds_match(db, model):
        return None
    latest = db.scalar(select(Reading).where(Reading.session_id == session_id).order_by(Reading.measured_at.desc(), Reading.id.desc()).limit(1))
    if latest is None or latest.measured_at < datetime.now(UTC) - timedelta(seconds=settings.reading_stale_after_seconds):
        return None
    readings = db.scalars(select(Reading).where(Reading.session_id == session_id, Reading.measured_at >= latest.measured_at - timedelta(seconds=WINDOW_SECONDS)).order_by(Reading.measured_at, Reading.id)).all()
    features = extract_features([{ "measured_at": r.measured_at, "quality": r.quality, "temperature_c": r.temperature_c,
                                  "heart_rate_bpm": r.heart_rate_bpm, "spo2_percent": r.spo2_percent} for r in readings])
    if features is None:
        return None
    prediction = predict(model, features)
    registry = db.scalar(select(ModelRegistry).where(ModelRegistry.model_key == model["model_key"], ModelRegistry.version == model["version"]))
    if registry is None:
        registry = ModelRegistry(model_key=model["model_key"], version=model["version"], task_type="synthetic_early_warning",
                                 status="candidate", artifact_uri=str(Path(settings.ai_model_path).resolve()), artifact_sha256=model["sha256"],
                                 metrics=model["metrics"], validation_notes=NOTICE)
        db.add(registry)
        db.flush()
    elif registry.artifact_sha256 != model["sha256"] or registry.status == "retired":
        logger.error("Model version was changed in place or retired; inference skipped")
        return None
    existing = db.scalar(select(RiskScore).where(RiskScore.session_id == session_id, RiskScore.model_registry_id == registry.id, RiskScore.data_window_end == latest.measured_at))
    if existing:
        return existing
    score = RiskScore(patient_id=session.patient_id, session_id=session_id, model_registry_id=registry.id,
                      score=prediction["score"], risk_category=prediction["risk_category"], target=prediction["target"],
                      data_window_start=readings[0].measured_at, data_window_end=latest.measured_at,
                      feature_snapshot=features, explanation={**prediction["explanation"], "validation_scope": "synthetic_only", "notice": NOTICE})
    db.add(score)
    db.flush()
    return score


def risk_response(db, session, latest=None, now=None):
    now = now or datetime.now(UTC)
    base = {"score": None, "validation_scope": "synthetic_only", "notice": NOTICE}
    if session is None or session.status != "active":
        return {**base, "status": "unmonitored"}
    model, availability = configured_model()
    if model is None:
        return {**base, "status": availability}
    if not thresholds_match(db, model):
        return {**base, "status": "threshold_configuration_mismatch"}
    if latest is None:
        latest = db.scalar(select(Reading).where(Reading.session_id == session.id).order_by(Reading.measured_at.desc(), Reading.id.desc()).limit(1))
    if latest is None:
        return {**base, "status": "insufficient_data"}
    if latest.measured_at < now - timedelta(seconds=settings.reading_stale_after_seconds):
        return {**base, "status": "stale", "last_measured_at": latest.measured_at}
    row = db.scalar(select(RiskScore).join(ModelRegistry, RiskScore.model_registry_id == ModelRegistry.id).where(
        RiskScore.session_id == session.id, RiskScore.data_window_end == latest.measured_at,
        ModelRegistry.model_key == model["model_key"], ModelRegistry.version == model["version"],
        ModelRegistry.artifact_sha256 == model["sha256"], ModelRegistry.status != "retired").order_by(RiskScore.id.desc()).limit(1))
    if row is None:
        return {**base, "status": "insufficient_data"}
    return {"status": "prototype", "score": float(row.score), "risk_category": row.risk_category,
            "warning": float(row.score) >= model["decision_threshold"], "model_version": model["version"],
            "target": row.target, "validation_scope": "synthetic_only", "notice": NOTICE,
            "data_window_start": row.data_window_start, "data_window_end": row.data_window_end,
            "computed_at": row.computed_at, "explanation": row.explanation}


def thresholds_match(db, model):
    values = active_thresholds(db).values
    return all(values.get(k) == v for k, v in model["event_thresholds"].items())
