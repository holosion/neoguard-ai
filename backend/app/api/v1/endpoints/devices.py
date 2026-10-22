from datetime import UTC, datetime, timedelta
from math import ceil
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AuthenticatedDevice, CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.core.security import hash_device_secret, issue_device_secret
from app.models import (
    ComponentHealthLog,
    Clinic,
    Device,
    DeviceComponent,
    DeviceCredential,
    DeviceTelemetry,
    MonitoringSession,
    Reading,
    User,
)
from app.schemas.resources import (
    DeviceCreate,
    DeviceCreated,
    DevicePublic,
    DeviceSecretOut,
    DeviceUpdate,
    DeviceSyncIn,
    DeviceSyncOut,
    DeviceSessionOut,
    SyncItemResult,
    TelemetryPublic,
)
from app.services.alerts import active_thresholds, create_threshold_alerts
from app.services.audit import record_audit
from app.services.risk import score_session

router = APIRouter(prefix="/devices", tags=["devices"])
logger = logging.getLogger(__name__)


@router.get("/runtime")
def device_runtime(db: DbSession, device: AuthenticatedDevice):
    """Authenticated provisioning context; queued events retain their original session."""
    session = db.scalar(select(MonitoringSession).where(
        MonitoringSession.device_id == device.id, MonitoringSession.status == "active"))
    thresholds = active_thresholds(db)
    return {
        "device_code": device.device_code,
        "session_id": session.id if session else None,
        "session_started_unix": int(session.started_at.timestamp()) if session else None,
        "server_time_unix": int(datetime.now(UTC).timestamp()),
        "thresholds": thresholds.values,
        "threshold_provenance": thresholds.provenance,
    }


@router.get("", response_model=list[DevicePublic])
def list_devices(
    db: DbSession,
    user: CurrentUser,
    response: Response,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    scope = True if user.role == "admin" else Device.clinic_id == user.clinic_id
    total = db.scalar(select(func.count(Device.id)).where(scope)) or 0
    items = db.scalars(select(Device).where(scope).order_by(Device.device_code).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(items)) if offset + len(items) < total else ""
    return items


@router.get("/current-session", response_model=DeviceSessionOut)
def current_device_session(db: DbSession, device: AuthenticatedDevice):
    """Let an authenticated device discover the session assigned by clinical staff."""
    session = db.scalar(
        select(MonitoringSession).where(
            MonitoringSession.device_id == device.id,
            MonitoringSession.status == "active",
        )
    )
    return DeviceSessionOut(device_code=device.device_code, session_id=session.id if session else None)


@router.post("", response_model=DeviceCreated, status_code=201)
def create_device(
    payload: DeviceCreate,
    db: DbSession,
    user: User = Depends(require_roles("admin")),
):
    if db.scalar(select(Device).where(Device.device_code == payload.device_code)):
        raise HTTPException(status_code=409, detail="Device code already exists")
    clinic = db.get(Clinic, payload.clinic_id) if payload.clinic_id is not None else None
    if clinic is None or not clinic.is_active:
        raise HTTPException(status_code=422, detail="clinic_id for an active clinic is required")
    device = Device(
        clinic_id=clinic.id,
        device_code=payload.device_code,
        name=payload.name,
        status=payload.status,
        hardware_version=payload.hardware_version,
        location=payload.location,
    )
    secret = issue_device_secret()
    db.add(device)
    db.flush()
    for component in payload.components:
        db.add(DeviceComponent(device_id=device.id, **component.model_dump()))
    db.add(DeviceCredential(device_id=device.id, secret_hash=hash_device_secret(secret)))
    record_audit(db, user_id=user.id, action="create_device", resource_type="device", resource_id=device.id)
    db.commit()
    db.refresh(device)
    return DeviceCreated(**DevicePublic.model_validate(device).model_dump(), device_secret=secret)


@router.get("/{device_id}", response_model=DevicePublic)
def get_device(device_id: int, db: DbSession, user: CurrentUser):
    scope = True if user.role == "admin" else Device.clinic_id == user.clinic_id
    device = db.scalar(select(Device).where(Device.id == device_id, scope))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.patch("/{device_id}", response_model=DevicePublic)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: DbSession,
    user: User = Depends(require_roles("admin")),
):
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("status") == "retired":
        active_session = db.scalar(
            select(MonitoringSession).where(
                MonitoringSession.device_id == device.id,
                MonitoringSession.status == "active",
            ).with_for_update()
        )
        if active_session is not None:
            active_session.status = "stopped"
            active_session.ended_at = datetime.now(UTC)
            record_audit(db, user_id=user.id, action="stop_session_device_retired", resource_type="session", resource_id=active_session.id)
    elif updates.get("status") not in (None, "active", device.status):
        active_session_id = db.scalar(
            select(MonitoringSession.id).where(MonitoringSession.device_id == device.id, MonitoringSession.status == "active")
        )
        if active_session_id is not None:
            raise HTTPException(status_code=409, detail="Stop the device's active monitoring session before changing its status.")
    for key, value in updates.items():
        setattr(device, key, value)
    record_audit(db, user_id=user.id, action="update_device", resource_type="device", resource_id=device.id)
    db.commit()
    db.refresh(device)
    return device


@router.post("/{device_id}/rotate-secret", response_model=DeviceSecretOut)
def rotate_device_secret(
    device_id: int,
    db: DbSession,
    user: User = Depends(require_roles("admin")),
):
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    credential = db.scalar(select(DeviceCredential).where(DeviceCredential.device_id == device.id))
    if credential is None:
        raise HTTPException(status_code=409, detail="Device has no credential to rotate")
    secret = issue_device_secret()
    credential.secret_hash = hash_device_secret(secret)
    credential.is_active = True
    credential.revoked_at = None
    credential.created_at = datetime.now(UTC)
    record_audit(db, user_id=user.id, action="rotate_device_secret", resource_type="device", resource_id=device.id)
    db.commit()
    return DeviceSecretOut(device_code=device.device_code, device_secret=secret, created_at=credential.created_at)


@router.post("/sync", response_model=DeviceSyncOut)
def sync_device(payload: DeviceSyncIn, db: DbSession, device: AuthenticatedDevice):
    if payload.device_code != device.device_code:
        raise HTTPException(status_code=403, detail="Payload device_code does not match authenticated device")
    device = db.scalar(select(Device).where(Device.id == device.id).with_for_update())
    if device is None or device.status != "active":
        raise HTTPException(status_code=403, detail="Device is not active")
    now = datetime.now(UTC)
    if device.last_sync_received_at is not None:
        elapsed = (now - device.last_sync_received_at).total_seconds()
        minimum = settings.device_sync_min_interval_seconds
        if elapsed < minimum:
            retry_after = max(1, ceil(minimum - elapsed))
            raise HTTPException(
                status_code=429,
                detail="Device sync rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
    device.last_seen_online = now
    device.last_sync_received_at = now
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version

    threshold_values = active_thresholds(db)
    results: list[SyncItemResult] = []
    event_ids = list({item.event_id for item in payload.readings})
    existing_rows = db.scalars(
        select(Reading).where(
            Reading.device_id == device.id,
            Reading.device_event_id.in_(event_ids),
        )
    ).all() if event_ids else []
    existing_by_event = {row.device_event_id: row for row in existing_rows}
    session_ids = sorted({item.session_id for item in payload.readings})
    sessions = db.scalars(select(MonitoringSession).where(MonitoringSession.id.in_(session_ids)).order_by(MonitoringSession.id).with_for_update()).all() if session_ids else []
    sessions_by_id = {s.id: s for s in sessions}
    changed_sessions = set()
    indexed_results = {}
    # Replay in observation order; response order still matches the device batch.
    for index, item in sorted(enumerate(payload.readings), key=lambda pair: pair[1].measured_at):
        existing = existing_by_event.get(item.event_id)
        if existing is not None:
            same = (existing.session_id == item.session_id and existing.measured_at == item.measured_at
                    and existing.heart_rate_bpm == item.heart_rate_bpm and existing.spo2_percent == item.spo2_percent
                    and (float(existing.temperature_c) if existing.temperature_c is not None else None) == item.temperature_c
                    and existing.quality == item.quality)
            indexed_results[index] = SyncItemResult(event_id=item.event_id, status="duplicate" if same else "rejected",
                                                   reading_id=existing.id if same else None,
                                                   reason=None if same else "Event ID was reused with different data")
            continue
        session = sessions_by_id.get(item.session_id)
        reason = validate_reading_session(item, session, device.id, now)
        if reason:
            indexed_results[index] = SyncItemResult(event_id=item.event_id, status="rejected", reason=reason)
            continue
        reading = Reading(
            session_id=session.id,
            device_id=device.id,
            device_event_id=item.event_id,
            measured_at=item.measured_at,
            heart_rate_bpm=item.heart_rate_bpm,
            spo2_percent=item.spo2_percent,
            temperature_c=item.temperature_c,
            quality=item.quality,
        )
        db.add(reading)
        db.flush()
        create_threshold_alerts(db, reading, threshold_values)
        changed_sessions.add(session.id)
        existing_by_event[item.event_id] = reading
        indexed_results[index] = SyncItemResult(event_id=item.event_id, status="accepted", reading_id=reading.id)

    results = [indexed_results[i] for i in range(len(payload.readings))]

    if payload.telemetry:
        telemetry = payload.telemetry
        db.add(
            DeviceTelemetry(
                device_id=device.id,
                reported_at=telemetry.reported_at,
                battery_percent=telemetry.battery_percent,
                wifi_rssi_dbm=telemetry.wifi_rssi_dbm,
                uptime_seconds=telemetry.uptime_seconds,
            )
        )

    for check in payload.component_checks:
        component = db.scalar(
            select(DeviceComponent).where(
                DeviceComponent.device_id == device.id,
                DeviceComponent.component_type == check.component_type,
            )
        )
        if component is None:
            db.rollback()
            raise HTTPException(status_code=422, detail=f"Unregistered component: {check.component_type}")
        db.add(
            ComponentHealthLog(
                device_id=device.id,
                component_id=component.id,
                checked_at=check.checked_at,
                status=check.status,
                error_code=check.error_code,
                details=check.details,
            )
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sync conflicted with another device operation; retry the batch") from exc
    # AI has its own transaction. Failure cannot roll back acknowledged sensor data.
    if changed_sessions:
        try:
            for session_id in sorted(changed_sessions):
                score_session(db, session_id)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Prototype scoring failed after readings were safely committed")
    return DeviceSyncOut(device_code=device.device_code, received_at=now, readings=results)


@router.get("/{device_id}/telemetry", response_model=list[TelemetryPublic])
def device_telemetry(
    device_id: int,
    db: DbSession,
    user: CurrentUser,
    response: Response,
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    scope = True if user.role == "admin" else Device.clinic_id == user.clinic_id
    if db.scalar(select(Device.id).where(Device.id == device_id, scope)) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if (start is not None and start.tzinfo is None) or (end is not None and end.tzinfo is None):
        raise HTTPException(status_code=422, detail="from and to must include a timezone")
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="from must be earlier than or equal to to")
    query = select(DeviceTelemetry).where(DeviceTelemetry.device_id == device_id)
    if start is not None:
        query = query.where(DeviceTelemetry.reported_at >= start)
    if end is not None:
        query = query.where(DeviceTelemetry.reported_at <= end)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.scalars(query.order_by(DeviceTelemetry.reported_at.desc(), DeviceTelemetry.id.desc()).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(items)) if offset + len(items) < total else ""
    return list(reversed(items))


def validate_reading_session(item, session, device_id, now):
    if session is None or session.device_id != device_id:
        return "Session does not belong to this device"
    if item.measured_at > now + timedelta(minutes=5):
        return "Measurement timestamp is too far in the future"
    if item.measured_at < session.started_at:
        return "Measurement predates its monitoring session"
    if session.ended_at is not None and item.measured_at > session.ended_at:
        return "Measurement is after its monitoring session ended"
    return None
