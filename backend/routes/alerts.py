from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_database
from backend.models import Alert, AuditLog
from backend.schemas import AlertResponse, AlertStatusUpdate
from backend.auth_security import CurrentUser, get_current_user


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
)


DatabaseSession = Annotated[Session, Depends(get_database)]


@router.get(
    "/",
    response_model=list[AlertResponse],
    dependencies=[Depends(get_current_user)],
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
    request: Request,
    current_user: CurrentUser,
    database: DatabaseSession,
):
    alert = database.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )

    previous_status = alert.status
    alert.status = status_update.status

    audit_entry = AuditLog(
        user_id=current_user.id,
        action="alert.status_changed",
        resource_type="alert",
        resource_id=str(alert.id),
        details={
            "previous_status": previous_status,
            "new_status": alert.status,
        },
        source_ip=request.client.host if request.client else None,
    )

    database.add(audit_entry)
    database.commit()
    database.refresh(alert)

    return alert