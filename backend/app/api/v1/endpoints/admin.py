from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.models import Alert, Clinic, ComponentHealthLog, Device, DeviceComponent, DeviceTelemetry, MonitoringSession, Reading
from app.schemas.resources import ClinicCreate, ClinicPublic
from app.services.audit import record_audit
from app.services.alerts import active_thresholds

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("admin"))])


@router.get("/clinics", response_model=list[ClinicPublic])
def list_clinics(db: DbSession, user: CurrentUser, active: bool | None = True):
    query = select(Clinic).order_by(Clinic.name)
    if active is not None:
        query = query.where(Clinic.is_active.is_(active))
    return db.scalars(query).all()


@router.post("/clinics", response_model=ClinicPublic, status_code=201)
def create_clinic(payload: ClinicCreate, db: DbSession, user: CurrentUser):
    if db.scalar(select(Clinic.id).where((Clinic.code == payload.code) | (Clinic.name == payload.name))):
        raise HTTPException(status_code=409, detail="A clinic with this name or code already exists")
    clinic = Clinic(name=payload.name, code=payload.code)
    db.add(clinic)
    db.flush()
    record_audit(db, user_id=user.id, action="create_clinic", resource_type="clinic", resource_id=clinic.id)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.get("/thresholds")
def get_thresholds(db: DbSession, user: CurrentUser):
    configured = active_thresholds(db)
    return [
        {
            "parameter": name,
            "value": item["value"],
            "unit": item["unit"],
            "source": item["source"],
            "version": item.get("version", item.get("threshold_id", "code-default")),
            "effective_from": item.get("effective_from"),
        }
        for name, item in configured.provenance.items()
    ]


@router.get("/overview")
def overview(db: DbSession, user: CurrentUser):
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.reading_stale_after_seconds)
    active_sync_times = db.scalars(
        select(Device.last_sync_received_at)
        .join(MonitoringSession, MonitoringSession.device_id == Device.id)
        .where(MonitoringSession.status == "active")
    ).all()
    sync_lag_seconds = max(
        (now - synced_at).total_seconds() for synced_at in active_sync_times if synced_at is not None
    ) if any(synced_at is not None for synced_at in active_sync_times) else 0
    return {
        "devices": {
            "total": db.scalar(select(func.count(Device.id))) or 0,
            "active": db.scalar(select(func.count(Device.id)).where(Device.status == "active")) or 0,
            "online_recently": db.scalar(
                select(func.count(Device.id)).where(Device.last_seen_online >= stale_before)
            ) or 0,
        },
        "active_sessions": db.scalar(
            select(func.count(MonitoringSession.id)).where(MonitoringSession.status == "active")
        ) or 0,
        "unacknowledged_alerts": db.scalar(
            select(func.count(Alert.id)).where(Alert.acknowledged_at.is_(None))
        ) or 0,
        "latest_reading_at": db.scalar(select(func.max(Reading.measured_at))),
        "sync_lag_seconds": max(0, int(sync_lag_seconds)),
        "generated_at": now,
    }


@router.get("/device-health")
def device_health(
    db: DbSession,
    user: CurrentUser,
    response: Response,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    now = datetime.now(UTC)
    total = db.scalar(select(func.count(Device.id))) or 0
    devices = db.scalars(select(Device).order_by(Device.device_code).offset(offset).limit(limit)).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + len(devices)) if offset + len(devices) < total else ""
    device_ids = [device.id for device in devices]
    telemetry_ranked = select(
        DeviceTelemetry,
        func.row_number().over(
            partition_by=DeviceTelemetry.device_id,
            order_by=(DeviceTelemetry.reported_at.desc(), DeviceTelemetry.id.desc()),
        ).label("telemetry_rank"),
    ).where(DeviceTelemetry.device_id.in_(device_ids)).subquery() if device_ids else None
    latest_telemetry = {}
    if telemetry_ranked is not None:
        latest_telemetry = {
            row.device_id: row
            for row in db.execute(
                select(DeviceTelemetry).join(telemetry_ranked, DeviceTelemetry.id == telemetry_ranked.c.id).where(
                    telemetry_ranked.c.telemetry_rank == 1
                )
            ).scalars().all()
        }
    components = db.scalars(
        select(DeviceComponent).where(DeviceComponent.device_id.in_(device_ids)).order_by(
            DeviceComponent.device_id, DeviceComponent.component_type
        )
    ).all() if device_ids else []
    component_ids = [component.id for component in components]
    checks_ranked = select(
        ComponentHealthLog,
        func.row_number().over(
            partition_by=ComponentHealthLog.component_id,
            order_by=(ComponentHealthLog.checked_at.desc(), ComponentHealthLog.id.desc()),
        ).label("check_rank"),
    ).where(ComponentHealthLog.component_id.in_(component_ids)).subquery() if component_ids else None
    latest_checks = {}
    if checks_ranked is not None:
        latest_checks = {
            row.component_id: row
            for row in db.execute(
                select(ComponentHealthLog).join(
                    checks_ranked, ComponentHealthLog.id == checks_ranked.c.id
                ).where(checks_ranked.c.check_rank == 1)
            ).scalars().all()
        }
    components_by_device = {}
    for component in components:
        check = latest_checks.get(component.id)
        components_by_device.setdefault(component.device_id, []).append({
            "component_id": component.id,
            "component_type": component.component_type,
            "pin_or_address": component.pin_or_address,
            "is_critical": component.is_critical,
            "status": check.status if check else "not_checked",
            "checked_at": check.checked_at if check else None,
            "received_at": check.received_at if check else None,
            "error_code": check.error_code if check else None,
            "details": check.details if check else None,
        })
    response = []
    for device in devices:
        telemetry = latest_telemetry.get(device.id)
        last_contact = device.last_seen_online
        response.append(
            {
                "device_id": device.id,
                "device_code": device.device_code,
                "status": device.status,
                "last_seen_online": last_contact,
                "connection_status": (
                    "unknown" if last_contact is None else
                    "stale" if last_contact < now - timedelta(seconds=settings.reading_stale_after_seconds) else "online"
                ),
                "latest_telemetry": (
                    {
                        "reported_at": telemetry.reported_at,
                        "received_at": telemetry.received_at,
                        "battery_percent": telemetry.battery_percent,
                        "wifi_rssi_dbm": telemetry.wifi_rssi_dbm,
                        "uptime_seconds": telemetry.uptime_seconds,
                    }
                    if telemetry else None
                ),
                "components": components_by_device.get(device.id, []),
            }
        )
    return response
