from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_security import get_current_user
from backend.database import get_database
from backend.models import Alert, Device, SecurityEvent
from backend.schemas import (
    DeviceHeartbeat,
    DeviceRegistration,
    DeviceResponse,
)
from backend.security import require_agent_api_key


router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
)


DEVICE_OFFLINE_AFTER = timedelta(minutes=5)
DatabaseSession = Annotated[Session, Depends(get_database)]


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

