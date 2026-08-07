from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_security import get_current_user
from backend.database import get_database
from backend.models import Alert, Device, DeviceTelemetry, SecurityEvent
from backend.schemas import (
    DeviceHeartbeat,
    DeviceRegistration,
    DeviceResponse,
    DeviceTelemetryCreate,
    DeviceTelemetryResponse,
)
from backend.security import require_agent_api_key


router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
)


DEVICE_OFFLINE_AFTER = timedelta(minutes=5)
CPU_ALERT_THRESHOLD = 90.0
MEMORY_ALERT_THRESHOLD = 90.0
DISK_FREE_ALERT_THRESHOLD = 10.0
DatabaseSession = Annotated[Session, Depends(get_database)]

def update_device_health_alert(
    database: Session,
    device: Device,
    *,
    rule_id: str,
    triggered: bool,
    title: str,
    description: str,
    message: str,
    raw_data: dict,
) -> None:
    active_alerts = database.scalars(
        select(Alert)
        .join(
            SecurityEvent,
            Alert.security_event_id == SecurityEvent.id,
        )
        .where(
            SecurityEvent.device_id == device.id,
            Alert.rule_id == rule_id,
            Alert.status.in_(["open", "investigating"]),
        )
    ).all()

    if not triggered:
        for active_alert in active_alerts:
            active_alert.status = "resolved"

        return

    if active_alerts:
        return

    health_event = SecurityEvent(
        device_id=device.id,
        windows_event_id=0,
        record_id=None,
        log_name="Watchtower",
        provider="Watchtower Health Monitor",
        level="Warning",
        message=message,
        occurred_at=datetime.now(timezone.utc),
        raw_data=raw_data,
    )

    database.add(health_event)
    database.flush()

    database.add(
        Alert(
            security_event_id=health_event.id,
            rule_id=rule_id,
            title=title,
            description=description,
            severity="high",
            status="open",
        )
    )


@router.post(
    "/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_agent_api_key)],
)
def register_device(
    device_data: DeviceRegistration,
    database: DatabaseSession,
):
    device = database.scalar(
        select(Device).where(Device.device_id == device_data.device_id)
    )

    current_time = datetime.now(timezone.utc)

    if device:
        device.hostname = device_data.hostname
        device.operating_system = device_data.operating_system
        device.ip_address = device_data.ip_address
        device.agent_version = device_data.agent_version
        device.status = "online"
        device.last_seen = current_time
    else:
        device = Device(
            **device_data.model_dump(),
            status="online",
            first_seen=current_time,
            last_seen=current_time,
        )
        database.add(device)

    database.commit()
    database.refresh(device)

    return device

@router.get(
    "/",
    response_model=list[DeviceResponse],
    dependencies=[Depends(get_current_user)],
)
def list_devices(database: DatabaseSession):
    devices = list(
        database.scalars(
            select(Device).order_by(Device.hostname)
        ).all()
    )

    current_time = datetime.now(timezone.utc)
    status_changed = False

    for device in devices:
        last_seen = device.last_seen

        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        if (
            current_time - last_seen >= DEVICE_OFFLINE_AFTER
            and device.status != "offline"
        ):
            device.status = "offline"
            status_changed = True

            offline_event = SecurityEvent(
                device_id=device.id,
                windows_event_id=0,
                record_id=None,
                log_name="Watchtower",
                provider="Watchtower Device Monitor",
                level="Warning",
                message=(
                    f"Device {device.hostname} stopped sending heartbeats."
                ),
                occurred_at=current_time,
                raw_data={
                    "device_id": device.device_id,
                    "last_seen": last_seen.isoformat(),
                },
            )

            database.add(offline_event)
            database.flush()

            database.add(
                Alert(
                    security_event_id=offline_event.id,
                    rule_id="device-offline",
                    title=f"Device offline: {device.hostname}",
                    description=(
                        f"No heartbeat was received from {device.hostname} "
                        f"for at least five minutes."
                    ),
                    severity="high",
                    status="open",
                )
            )

    if status_changed:
        database.commit()

    return devices

@router.post(
    "/{device_id}/heartbeat",
    response_model=DeviceResponse,
    dependencies=[Depends(require_agent_api_key)],
)
def record_device_heartbeat(
    device_id: str,
    heartbeat: DeviceHeartbeat,
    database: DatabaseSession,
):
    device = database.scalar(
        select(Device).where(Device.device_id == device_id)
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found.",
        )

    device.last_seen = datetime.now(timezone.utc)
    device.status = "online"

    if heartbeat.agent_version is not None:
        device.agent_version = heartbeat.agent_version
    offline_alerts = database.scalars(
        select(Alert)
        .join(
            SecurityEvent,
            Alert.security_event_id == SecurityEvent.id,
        )
        .where(
            SecurityEvent.device_id == device.id,
            Alert.rule_id == "device-offline",
            Alert.status.in_(["open", "investigating"]),
        )
    ).all()

    for offline_alert in offline_alerts:
        offline_alert.status = "resolved"

    database.commit()
    database.refresh(device)

    return device

@router.post(
    "/{device_id}/telemetry",
    response_model=DeviceTelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_agent_api_key)],
)
def record_device_telemetry(
    device_id: str,
    telemetry: DeviceTelemetryCreate,
    database: DatabaseSession,
):
    device = database.scalar(
        select(Device).where(Device.device_id == device_id)
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found.",
        )

    if telemetry.disk_free_gb > telemetry.disk_total_gb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Free disk space cannot exceed total disk space.",
        )

    telemetry_record = DeviceTelemetry(
        device_id=device.id,
        **telemetry.model_dump(),
    )

    database.add(telemetry_record)
    disk_free_percent = (
        telemetry.disk_free_gb /
        telemetry.disk_total_gb
    ) * 100

    update_device_health_alert(
        database,
        device,
        rule_id="device-high-cpu",
        triggered=(
            telemetry.cpu_percent >= CPU_ALERT_THRESHOLD
        ),
        title=f"High CPU usage: {device.hostname}",
        description=(
            f"CPU usage reached {telemetry.cpu_percent:.1f}% "
            f"on {device.hostname}."
        ),
        message=(
            f"High CPU usage detected on {device.hostname}."
        ),
        raw_data={
            "cpu_percent": telemetry.cpu_percent,
            "threshold": CPU_ALERT_THRESHOLD,
        },
    )

    update_device_health_alert(
        database,
        device,
        rule_id="device-high-memory",
        triggered=(
            telemetry.memory_percent >=
            MEMORY_ALERT_THRESHOLD
        ),
        title=f"High memory usage: {device.hostname}",
        description=(
            f"Memory usage reached "
            f"{telemetry.memory_percent:.1f}% "
            f"on {device.hostname}."
        ),
        message=(
            f"High memory usage detected on {device.hostname}."
        ),
        raw_data={
            "memory_percent": telemetry.memory_percent,
            "threshold": MEMORY_ALERT_THRESHOLD,
        },
    )

    update_device_health_alert(
        database,
        device,
        rule_id="device-low-disk",
        triggered=(
            disk_free_percent <=
            DISK_FREE_ALERT_THRESHOLD
        ),
        title=f"Low disk space: {device.hostname}",
        description=(
            f"Disk free space dropped to "
            f"{disk_free_percent:.1f}% "
            f"on {device.hostname}."
        ),
        message=(
            f"Low disk space detected on {device.hostname}."
        ),
        raw_data={
            "disk_free_gb": telemetry.disk_free_gb,
            "disk_total_gb": telemetry.disk_total_gb,
            "disk_free_percent": disk_free_percent,
            "threshold": DISK_FREE_ALERT_THRESHOLD,
        },
    )
    database.commit()
    database.refresh(telemetry_record)

    return telemetry_record

@router.get(
    "/{device_id}/telemetry/latest",
    response_model=DeviceTelemetryResponse | None,
    dependencies=[Depends(get_current_user)],
)
def get_latest_device_telemetry(
    device_id: str,
    database: DatabaseSession,
):
    device = database.scalar(
        select(Device).where(Device.device_id == device_id)
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found.",
        )

    return database.scalar(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device.id)
        .order_by(
            DeviceTelemetry.collected_at.desc(),
            DeviceTelemetry.id.desc(),
        )
        .limit(1)
    )

