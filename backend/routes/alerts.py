from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_database
from backend.models import Alert
from backend.schemas import AlertResponse, AlertStatusUpdate


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
)


DatabaseSession = Annotated[Session, Depends(get_database)]


@router.get(
    "/",
    response_model=list[AlertResponse],
)
def list_alerts(
    database: DatabaseSession,
    severity: str | None = None,
    alert_status: str | None = None,
    limit: int = 100,
):
    limit = max(1, min(limit, 500))

    query = select(Alert)

    if severity:
        query = query.where(Alert.severity == severity.lower())

    if alert_status:
        query = query.where(Alert.status == alert_status.lower())

    query = query.order_by(Alert.created_at.desc()).limit(limit)

    alerts = database.scalars(query).all()

    return list(alerts)

@router.patch(
    "/{alert_id}/status",
    response_model=AlertResponse,
)
def update_alert_status(
    alert_id: int,
    status_update: AlertStatusUpdate,
    database: DatabaseSession,
):
    alert = database.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )

    alert.status = status_update.status

    database.commit()
    database.refresh(alert)

    return alert