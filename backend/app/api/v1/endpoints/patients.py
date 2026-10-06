from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.models import MonitoringSession, Patient, Reading, RiskProfile
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

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientListItem])
def list_patients(db: DbSession, user: CurrentUser):
    patients = db.scalars(select(Patient).order_by(Patient.patient_code)).all()
    result = []
    now = datetime.now(UTC)
    for patient in patients:
        session = db.scalar(
            select(MonitoringSession).where(
                MonitoringSession.patient_id == patient.id,
                MonitoringSession.status == "active",
            )
        )
        latest = None
        status_value = "unmonitored"
        if session:
            latest = db.scalar(
                select(Reading)
                .where(Reading.session_id == session.id)
                .order_by(Reading.measured_at.desc())
                .limit(1)
            )
            status_value = "empty" if latest is None else (
                "stale" if latest.measured_at < now - timedelta(seconds=settings.reading_stale_after_seconds) else "fresh"
            )
        result.append(
            PatientListItem(
                patient=patient,
                active_session=session,
                latest_reading=latest,
                data_status=status_value,
            )
        )
    return result


@router.post("", response_model=PatientPublic, status_code=201)
def create_patient(payload: PatientCreate, db: DbSession, user: CurrentUser = Depends(require_roles("admin", "clinician"))):
    if db.scalar(select(Patient).where(Patient.patient_code == payload.patient_code)):
        raise HTTPException(status_code=409, detail="Patient code already exists")
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.flush()
    record_audit(db, user_id=user.id, action="create_patient", resource_type="patient", resource_id=patient.id)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientPublic)
def get_patient(patient_id: int, db: DbSession, user: CurrentUser):
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientPublic)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: DbSession,
    user: CurrentUser = Depends(require_roles("admin", "clinician")),
):
    patient = db.get(Patient, patient_id)
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
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return db.scalar(select(RiskProfile).where(RiskProfile.patient_id == patient_id))


@router.put("/{patient_id}/risk-profile", response_model=RiskProfilePublic)
def upsert_risk_profile(
    patient_id: int,
    payload: RiskProfileUpsert,
    db: DbSession,
    user: CurrentUser = Depends(require_roles("admin", "clinician")),
):
    if db.get(Patient, patient_id) is None:
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
    user: CurrentUser,
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=5000),
):
    if start is not None and start.tzinfo is None:
        raise HTTPException(status_code=422, detail="from must include a timezone")
    if end is not None and end.tzinfo is None:
        raise HTTPException(status_code=422, detail="to must include a timezone")
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="from must be earlier than or equal to to")
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    sessions = db.scalars(select(MonitoringSession).where(MonitoringSession.patient_id == patient_id)).all()
    session_ids = [session.id for session in sessions]
    readings = []
    if session_ids:
        query = select(Reading).where(Reading.session_id.in_(session_ids))
        if start:
            query = query.where(Reading.measured_at >= start)
        if end:
            query = query.where(Reading.measured_at <= end)
        readings = list(db.scalars(query.order_by(Reading.measured_at.desc()).limit(limit)).all())
    now = datetime.now(UTC)
    latest = readings[0] if readings else None
    data_status = "empty" if latest is None else (
        "stale" if latest.measured_at < now - timedelta(seconds=settings.reading_stale_after_seconds) else "fresh"
    )
    return ReadingHistory(
        patient_code=patient.patient_code,
        readings=list(reversed(readings)),
        data_status=data_status,
        last_measured_at=latest.measured_at if latest else None,
        last_synced_at=latest.received_at if latest else None,
        stale_after_seconds=settings.reading_stale_after_seconds,
    )


@router.get("/{patient_id}/risk-score")
def patient_risk_score(patient_id: int, db: DbSession, user: CurrentUser):
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    # The model is intentionally not enabled until it has a documented training/validation pipeline.
    return {"patient_id": patient_id, "status": "not_available", "score": None, "message": "No validated risk model is configured."}
