from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_security import get_current_user
from backend.database import get_database
from backend.models import Device
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
    devices = database.scalars(
        select(Device).order_by(Device.hostname)
    ).all()

    return list(devices)

@router.post(
    "/{device_id}/heartbeat",
    response_model=DeviceResponse,
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

    database.commit()
    database.refresh(device)

    return device

