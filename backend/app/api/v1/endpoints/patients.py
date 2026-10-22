from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.models import Clinic, Device, MonitoringSession, Patient, Reading, RiskProfile, User
from app.schemas.resources import (
    PatientCreate,
    PatientListItem,
    PatientPublic,
    PatientUpdate,
    ReadingHistory,
    RiskProfilePublic,
    RiskProfileUpsert,
)
from app.services.audit import record_audit
from app.services.risk import risk_response

router = APIRouter(prefix="/patients", tags=["patients"])


def patient_scope(user: User):
    return True if user.role == "admin" else Patient.clinic_id == user.clinic_id


@router.get("", response_model=list[PatientListItem])
def list_patients(
    db: DbSession,
    response: Response,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    scope = patient_scope(user)
    total = db.scalar(select(func.count(Patient.id)).where(scope)) or 0
    patients = db.scalars(select(Patient).where(scope).order_by(Patient.patient_code).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(patients)) if offset + len(patients) < total else ""
    patient_ids = [patient.id for patient in patients]
    sessions = db.scalars(
        select(MonitoringSession).where(
            MonitoringSession.patient_id.in_(patient_ids), MonitoringSession.status == "active"
        )
    ).all() if patient_ids else []
    session_by_patient = {session.patient_id: session for session in sessions}
    session_ids = [session.id for session in sessions]
    ranked_readings = (
        select(
            Reading,
            func.row_number().over(
                partition_by=Reading.session_id,
                order_by=(Reading.measured_at.desc(), Reading.id.desc()),
            ).label("reading_rank"),
        ).where(Reading.session_id.in_(session_ids)).subquery()
        if session_ids and user.role != "admin" else None
    )
    latest_by_session = {}
    if ranked_readings is not None:
        latest_rows = db.execute(
            select(Reading).join(ranked_readings, Reading.id == ranked_readings.c.id).where(
                ranked_readings.c.reading_rank == 1
            )
        ).scalars().all()
        latest_by_session = {reading.session_id: reading for reading in latest_rows}
    result = []
    now = datetime.now(UTC)
    for patient in patients:
        session = session_by_patient.get(patient.id)
        latest = None
        status_value = "unmonitored"
        if session:
            if user.role == "admin":
                status_value = "empty"
            else:
                latest = latest_by_session.get(session.id)
                status_value = "empty" if latest is None else (
                    "stale" if latest.measured_at < now - timedelta(seconds=settings.reading_stale_after_seconds) else "fresh"
                )
        result.append(
            PatientListItem(
                patient=patient,
                active_session=session,
                latest_reading=None if user.role == "admin" else latest,
                data_status=status_value,
                risk=None if user.role == "admin" else risk_response(db, session, latest=latest, now=now),
            )
        )
    return result


@router.post("", response_model=PatientPublic, status_code=201)
def create_patient(
    payload: PatientCreate,
    db: DbSession,
    user: User = Depends(require_roles("admin", "clinician")),
):
    clinic_id = user.clinic_id if user.role != "admin" else payload.clinic_id
    if clinic_id is None:
        raise HTTPException(status_code=422, detail="clinic_id is required for a system administrator")
    clinic = db.get(Clinic, clinic_id)
    if clinic is None or not clinic.is_active:
        raise HTTPException(status_code=404, detail="Clinic not found")
    if db.scalar(select(Patient).where(Patient.clinic_id == clinic_id, Patient.patient_code == payload.patient_code)):
        raise HTTPException(status_code=409, detail="Patient code already exists")
    patient = Patient(**payload.model_dump(exclude={"clinic_id"}), clinic_id=clinic_id)
    db.add(patient)
    db.flush()
    record_audit(db, user_id=user.id, action="create_patient", resource_type="patient", resource_id=patient.id)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientPublic)
def get_patient(patient_id: int, db: DbSession, user: CurrentUser):
    patient = db.scalar(select(Patient).where(Patient.id == patient_id, patient_scope(user)))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientPublic)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: DbSession,
    user: User = Depends(require_roles("admin", "clinician")),
):
    patient = db.scalar(select(Patient).where(Patient.id == patient_id, patient_scope(user)))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    record_audit(db, user_id=user.id, action="update_patient", resource_type="patient", resource_id=patient.id)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}/risk-profile", response_model=RiskProfilePublic | None)
def get_risk_profile(patient_id: int, db: DbSession, user: CurrentUser):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Clinical risk profiles are available to clinical staff only")
    if db.scalar(select(Patient.id).where(Patient.id == patient_id, patient_scope(user))) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return db.scalar(select(RiskProfile).where(RiskProfile.patient_id == patient_id))


@router.put("/{patient_id}/risk-profile", response_model=RiskProfilePublic)
def upsert_risk_profile(
    patient_id: int,
    payload: RiskProfileUpsert,
    db: DbSession,
    user: User = Depends(require_roles("clinician")),
):
    if db.scalar(select(Patient.id).where(Patient.id == patient_id, patient_scope(user))) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    profile = db.scalar(select(RiskProfile).where(RiskProfile.patient_id == patient_id))
    if profile is None:
        profile = RiskProfile(patient_id=patient_id, **payload.model_dump(), updated_by_user_id=user.id)
        db.add(profile)
    else:
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
        profile.updated_by_user_id = user.id
    db.flush()
    record_audit(db, user_id=user.id, action="update_risk_profile", resource_type="risk_profile", resource_id=profile.id)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{patient_id}/readings", response_model=ReadingHistory)
def patient_readings(
    patient_id: int,
    db: DbSession,
    response: Response,
    user: CurrentUser,
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Patient readings are available to clinical staff only")
    if start is not None and start.tzinfo is None:
        raise HTTPException(status_code=422, detail="from must include a timezone")
    if end is not None and end.tzinfo is None:
        raise HTTPException(status_code=422, detail="to must include a timezone")
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="from must be earlier than or equal to to")
    patient = db.scalar(select(Patient).where(Patient.id == patient_id, patient_scope(user)))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    sessions = db.scalars(select(MonitoringSession).where(MonitoringSession.patient_id == patient_id)).all()
    session_ids = [session.id for session in sessions]
    readings = []
    query = select(Reading).where(Reading.session_id.in_(session_ids)) if session_ids else None
    if query is not None:
        if start:
            query = query.where(Reading.measured_at >= start)
        if end:
            query = query.where(Reading.measured_at <= end)
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        readings = list(db.scalars(query.order_by(Reading.measured_at.desc(), Reading.id.desc()).offset(offset).limit(limit)).all())
    else:
        total = 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(readings)) if offset + len(readings) < total else ""
    now = datetime.now(UTC)
    latest = readings[0] if readings else None
    data_status = "empty" if latest is None else (
        "stale" if latest.measured_at < now - timedelta(seconds=settings.reading_stale_after_seconds) else "fresh"
    )
    last_device_sync_at = db.scalar(
        select(func.max(Device.last_sync_received_at)).where(
            Device.id.in_(select(MonitoringSession.device_id).where(MonitoringSession.id.in_(session_ids)))
        )
    ) if session_ids else None
    last_received_at = db.scalar(
        select(func.max(Reading.received_at)).where(Reading.session_id.in_(session_ids))
    ) if session_ids else None
    return ReadingHistory(
        patient_code=patient.patient_code,
        readings=list(reversed(readings)),
        data_status=data_status,
        last_measured_at=latest.measured_at if latest else None,
        last_synced_at=last_received_at,
        last_device_sync_at=last_device_sync_at,
        stale_after_seconds=settings.reading_stale_after_seconds,
    )


@router.get("/{patient_id}/risk-score")
def patient_risk_score(patient_id: int, db: DbSession, user: CurrentUser):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Clinical risk scores are available to clinical staff only")
    if db.scalar(select(Patient.id).where(Patient.id == patient_id, patient_scope(user))) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    session = db.scalar(select(MonitoringSession).where(MonitoringSession.patient_id == patient_id, MonitoringSession.status == "active"))
    return {"patient_id": patient_id, **risk_response(db, session)}
