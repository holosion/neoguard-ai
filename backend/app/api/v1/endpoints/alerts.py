from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import Alert, MonitoringSession
from app.schemas.resources import AlertPublic
from app.services.audit import record_audit

router = APIRouter(prefix="/alerts", tags=["alerts"])




@router.get("", response_model=list[AlertPublic])
def list_alerts(
    db: DbSession,
    user: CurrentUser,
    response: Response,
    patient_id: int | None = None,
    acknowledged: bool | None = None,
    severity: str | None = Query(default=None, pattern="^(low|medium|high|critical)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = select(Alert).join(MonitoringSession, Alert.session_id == MonitoringSession.id)
    if user.role != "admin":
        query = query.where(MonitoringSession.clinic_id == user.clinic_id)
    if acknowledged is not None:
        query = query.where(Alert.acknowledged_at.is_not(None) if acknowledged else Alert.acknowledged_at.is_(None))
    if severity:
        query = query.where(Alert.severity == severity)
    if patient_id is not None:
        query = query.where(MonitoringSession.patient_id == patient_id)
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(count_query) or 0
    items = db.scalars(query.order_by(Alert.created_at.desc(), Alert.id.desc()).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(items)) if offset + len(items) < total else ""
    return items


@router.post("/{alert_id}/acknowledge", response_model=AlertPublic)
def acknowledge_alert(alert_id: int, db: DbSession, user: CurrentUser):
    scope = True if user.role == "admin" else MonitoringSession.clinic_id == user.clinic_id
    alert = db.scalar(select(Alert).join(MonitoringSession, Alert.session_id == MonitoringSession.id).where(Alert.id == alert_id, scope).with_for_update())
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by_user_id = user.id
        record_audit(db, user_id=user.id, action="acknowledge_alert", resource_type="alert", resource_id=alert.id)
        db.commit()
        db.refresh(alert)
    return alert
