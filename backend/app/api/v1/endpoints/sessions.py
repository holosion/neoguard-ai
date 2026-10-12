from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import Device, MonitoringSession, Patient, User
from app.schemas.resources import SessionCreate, SessionPublic
from app.services.audit import record_audit

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionPublic])
def list_sessions(db: DbSession, user: CurrentUser):
    return db.scalars(select(MonitoringSession).order_by(MonitoringSession.started_at.desc()).limit(500)).all()


@router.post("", response_model=SessionPublic, status_code=201)
def start_session(
    payload: SessionCreate,
    db: DbSession,
    user: User = Depends(require_roles("admin", "clinician")),
):
    device = db.scalar(select(Device).where(Device.id == payload.device_id).with_for_update())
    patient = db.get(Patient, payload.patient_id)
    if patient is None or device is None:
        raise HTTPException(status_code=404, detail="Patient or device not found")
    if device.status != "active":
        raise HTTPException(status_code=409, detail="Device must be active before starting a session")
    if db.scalar(select(MonitoringSession).where(MonitoringSession.patient_id == patient.id, MonitoringSession.status == "active")):
        raise HTTPException(status_code=409, detail="Patient already has an active monitoring session")
    if db.scalar(select(MonitoringSession).where(MonitoringSession.device_id == device.id, MonitoringSession.status == "active")):
        raise HTTPException(status_code=409, detail="Device already has an active monitoring session")
    session = MonitoringSession(patient_id=patient.id, device_id=device.id, started_by_user_id=user.id)
    db.add(session)
    try:
        db.flush()
        record_audit(db, user_id=user.id, action="start_session", resource_type="session", resource_id=session.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Patient or device was assigned concurrently") from exc
    db.refresh(session)
    return session


@router.post("/{session_id}/stop", response_model=SessionPublic)
def stop_session(
    session_id: int,
    db: DbSession,
    user: User = Depends(require_roles("admin", "clinician")),
):
    session = db.get(MonitoringSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    # Match sync/start lock order: device first, then session.
    db.scalar(select(Device).where(Device.id == session.device_id).with_for_update())
    session = db.scalar(select(MonitoringSession).where(MonitoringSession.id == session_id).with_for_update().execution_options(populate_existing=True))
    if session.status != "active":
        raise HTTPException(status_code=409, detail="Session is already closed")
    session.status = "stopped"
    from datetime import UTC, datetime

    session.ended_at = datetime.now(UTC)
    record_audit(db, user_id=user.id, action="stop_session", resource_type="session", resource_id=session.id)
    db.commit()
    db.refresh(session)
    return session
