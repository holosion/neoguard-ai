from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.models import Alert, Device, DeviceTelemetry, MonitoringSession, Reading

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
    response = []
    for device in devices:
        telemetry = db.scalar(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device.id)
            .order_by(DeviceTelemetry.reported_at.desc())
            .limit(1)
        )
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
            }
        )
    return response
