from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_security import AdminUser
from backend.database import get_database
from backend.models import AuditLog
from backend.schemas import AuditLogResponse


router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
)

DatabaseSession = Annotated[Session, Depends(get_database)]


@router.get(
    "/",
    response_model=list[AuditLogResponse],
)
def list_audit_logs(
    current_user: AdminUser,
    database: DatabaseSession,
    limit: int = 100,
):
    limit = max(1, min(limit, 500))

    audit_logs = database.scalars(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()

    return list(audit_logs)