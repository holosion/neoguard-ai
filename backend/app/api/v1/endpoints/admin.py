from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.models import Alert, ComponentHealthLog, Device, DeviceComponent, DeviceTelemetry, MonitoringSession, Reading

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("admin"))])


@router.get("/overview")
def overview(db: DbSession, user: CurrentUser):
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.reading_stale_after_seconds)
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
        "generated_at": now,
    }


@router.get("/device-health")
def device_health(db: DbSession, user: CurrentUser):
    now = datetime.now(UTC)
    devices = db.scalars(select(Device).order_by(Device.device_code)).all()
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
