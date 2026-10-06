from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import Alert, MonitoringSession
from app.schemas.resources import AlertPublic
from app.services.audit import record_audit

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertPublic])
def list_alerts(
    db: DbSession,
    user: CurrentUser,
    patient_id: int | None = None,
    acknowledged: bool | None = None,
    severity: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    limit: int = Query(default=100, ge=1, le=500),
):
    query = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if acknowledged is not None:
        query = query.where(Alert.acknowledged_at.is_not(None) if acknowledged else Alert.acknowledged_at.is_(None))
    if severity:
        query = query.where(Alert.severity == severity)
    if patient_id is not None:
        query = query.join(MonitoringSession, Alert.session_id == MonitoringSession.id).where(
            MonitoringSession.patient_id == patient_id
        )
    return db.scalars(query).all()


@router.post("/{alert_id}/acknowledge", response_model=AlertPublic)
def acknowledge_alert(alert_id: int, db: DbSession, user: CurrentUser):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by_user_id = user.id
        record_audit(db, user_id=user.id, action="acknowledge_alert", resource_type="alert", resource_id=alert.id)
        db.commit()
        db.refresh(alert)
    return alert
