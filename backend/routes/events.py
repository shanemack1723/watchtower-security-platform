from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_database
from backend.models import Device, SecurityEvent
from backend.schemas import SecurityEventCreate, SecurityEventResponse
from backend.detection_engine import evaluate_security_event
from backend.security import require_agent_api_key
from backend.auth_security import get_current_user


router = APIRouter(
    prefix="/events",
    tags=["Security Events"],
)


DatabaseSession = Annotated[Session, Depends(get_database)]


@router.post(
    "/",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_agent_api_key)],
)
def create_security_event(
    event_data: SecurityEventCreate,
    database: DatabaseSession,
):
    device = database.scalar(
        select(Device).where(Device.device_id == event_data.device_id)
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified device is not registered.",
        )

    if event_data.record_id is not None:
        existing_event = database.scalar(
            select(SecurityEvent).where(
                SecurityEvent.device_id == device.id,
                SecurityEvent.log_name == event_data.log_name,
                SecurityEvent.record_id == event_data.record_id,
            )
        )

        if existing_event is not None:
            return existing_event

    event_values = event_data.model_dump(exclude={"device_id"})

    security_event = SecurityEvent(
        device_id=device.id,
        **event_values,
    )

    database.add(security_event)
    database.commit()
    database.refresh(security_event)

    evaluate_security_event(
        security_event=security_event,
        database=database,
    )

    return security_event

@router.get(
    "/",
    response_model=list[SecurityEventResponse],
    dependencies=[Depends(get_current_user)],
)
def list_security_events(
    database: DatabaseSession,
    limit: int = 100,
):
    limit = max(1, min(limit, 500))

    events = database.scalars(
        select(SecurityEvent)
        .order_by(SecurityEvent.occurred_at.desc())
        .limit(limit)
    ).all()

    return list(events)