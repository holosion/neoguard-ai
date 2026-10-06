from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AuthenticatedDevice, CurrentUser, DbSession, require_roles
from app.core.security import hash_device_secret, issue_device_secret
from app.models import (
    ComponentHealthLog,
    Device,
    DeviceComponent,
    DeviceCredential,
    DeviceTelemetry,
    MonitoringSession,
    Reading,
)
from app.schemas.resources import (
    DeviceCreate,
    DeviceCreated,
    DevicePublic,
    DeviceUpdate,
    DeviceSyncIn,
    DeviceSyncOut,
    SyncItemResult,
)
from app.services.alerts import active_thresholds, create_threshold_alerts
from app.services.audit import record_audit

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DevicePublic])
def list_devices(db: DbSession, user: CurrentUser):
    return db.scalars(select(Device).order_by(Device.device_code)).all()


@router.post("", response_model=DeviceCreated, status_code=201)
def create_device(
    payload: DeviceCreate,
    db: DbSession,
    user: CurrentUser = Depends(require_roles("admin")),
):
    if db.scalar(select(Device).where(Device.device_code == payload.device_code)):
        raise HTTPException(status_code=409, detail="Device code already exists")
    device = Device(
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
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.patch("/{device_id}", response_model=DevicePublic)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: DbSession,
    user: CurrentUser = Depends(require_roles("admin")),
):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    record_audit(db, user_id=user.id, action="update_device", resource_type="device", resource_id=device.id)
    db.commit()
    db.refresh(device)
    return device


@router.post("/sync", response_model=DeviceSyncOut)
def sync_device(payload: DeviceSyncIn, db: DbSession, device: AuthenticatedDevice):
    if payload.device_code != device.device_code:
        raise HTTPException(status_code=403, detail="Payload device_code does not match authenticated device")
    session = db.scalar(
        select(MonitoringSession).where(
            MonitoringSession.device_id == device.id,
            MonitoringSession.status == "active",
        )
    )
    if session is None:
        raise HTTPException(status_code=409, detail="Device has no active monitoring session")

    now = datetime.now(UTC)
    threshold_values = active_thresholds(db)
    results: list[SyncItemResult] = []
    device.last_seen_online = now
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version

    for item in payload.readings:
        existing = db.scalar(
            select(Reading).where(
                Reading.device_id == device.id,
                Reading.device_event_id == item.event_id,
            )
        )
        if existing:
            results.append(SyncItemResult(event_id=item.event_id, status="duplicate", reading_id=existing.id))
            continue
        if item.measured_at > now + timedelta(minutes=5):
            results.append(SyncItemResult(event_id=item.event_id, status="rejected", reason="Measurement timestamp is too far in the future"))
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
        results.append(SyncItemResult(event_id=item.event_id, status="accepted", reading_id=reading.id))

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
            component = DeviceComponent(device_id=device.id, component_type=check.component_type)
            db.add(component)
            db.flush()
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
    return DeviceSyncOut(device_code=device.device_code, received_at=now, readings=results)
