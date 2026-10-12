from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import Device, MonitoringSession, Patient, User
from app.schemas.resources import SessionCreate, SessionPublic
from app.services.audit import record_audit

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionPublic])
def list_sessions(
    db: DbSession,
    user: CurrentUser,
    response: Response,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    scope = True if user.role == "admin" else MonitoringSession.clinic_id == user.clinic_id
    total = db.scalar(select(func.count(MonitoringSession.id)).where(scope)) or 0
    items = db.scalars(select(MonitoringSession).where(scope).order_by(MonitoringSession.started_at.desc()).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(items)) if offset + len(items) < total else ""
    return items


@router.post("", response_model=SessionPublic, status_code=201)
def start_session(
    payload: SessionCreate,
    db: DbSession,
    user: User = Depends(require_roles("admin", "clinician")),
):
    scope_device = True if user.role == "admin" else Device.clinic_id == user.clinic_id
    scope_patient = True if user.role == "admin" else Patient.clinic_id == user.clinic_id
    device = db.scalar(select(Device).where(Device.id == payload.device_id, scope_device).with_for_update())
    patient = db.scalar(select(Patient).where(Patient.id == payload.patient_id, scope_patient))
    if patient is None or device is None:
        raise HTTPException(status_code=404, detail="Patient or device not found")
    if device.status != "active":
        raise HTTPException(status_code=409, detail="Device must be active before starting a session")
    if db.scalar(select(MonitoringSession).where(MonitoringSession.patient_id == patient.id, MonitoringSession.status == "active")):
        raise HTTPException(status_code=409, detail="Patient already has an active monitoring session")
    if db.scalar(select(MonitoringSession).where(MonitoringSession.device_id == device.id, MonitoringSession.status == "active")):
        raise HTTPException(status_code=409, detail="Device already has an active monitoring session")
    if patient.clinic_id != device.clinic_id:
        raise HTTPException(status_code=409, detail="Patient and device must belong to the same clinic")
    session = MonitoringSession(clinic_id=patient.clinic_id, patient_id=patient.id, device_id=device.id, started_by_user_id=user.id)
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
    scope = True if user.role == "admin" else MonitoringSession.clinic_id == user.clinic_id
    session = db.scalar(select(MonitoringSession).where(MonitoringSession.id == session_id, scope))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    # Match sync/start lock order: device first, then session.
    db.scalar(select(Device).where(Device.id == session.device_id).with_for_update())
    session = db.scalar(select(MonitoringSession).where(MonitoringSession.id == session_id, scope).with_for_update().execution_options(populate_existing=True))
    if session.status != "active":
        raise HTTPException(status_code=409, detail="Session is already closed")
    session.status = "stopped"
    from datetime import UTC, datetime

    session.ended_at = datetime.now(UTC)
    record_audit(db, user_id=user.id, action="stop_session", resource_type="session", resource_id=session.id)
    db.commit()
    db.refresh(session)
    return session
