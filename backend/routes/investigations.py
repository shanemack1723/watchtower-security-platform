from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_security import CurrentUser
from backend.database import get_database
from backend.models import (
    Alert,
    AlertAssignment,
    AlertNote,
    AuditLog,
    User,
)
from backend.schemas import (
    AlertAssignmentCreate,
    AlertAssignmentResponse,
    AlertNoteCreate,
    AlertNoteResponse,
)


router = APIRouter(
    prefix="/alerts",
    tags=["Investigations"],
)

DatabaseSession = Annotated[Session, Depends(get_database)]


@router.put(
    "/{alert_id}/assignment",
    response_model=AlertAssignmentResponse,
)
def assign_alert(
    alert_id: int,
    assignment_data: AlertAssignmentCreate,
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

    assigned_user = database.get(
        User,
        assignment_data.assigned_user_id,
    )

    if assigned_user is None or not assigned_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active user not found.",
        )

    assignment = database.scalar(
        select(AlertAssignment).where(
            AlertAssignment.alert_id == alert_id
        )
    )

    previous_user_id = None

    if assignment is None:
        assignment = AlertAssignment(
            alert_id=alert_id,
            assigned_user_id=assigned_user.id,
            assigned_by_user_id=current_user.id,
        )
        database.add(assignment)
    else:
        previous_user_id = assignment.assigned_user_id
        assignment.assigned_user_id = assigned_user.id
        assignment.assigned_by_user_id = current_user.id

    database.add(
        AuditLog(
            user_id=current_user.id,
            action="alert.assigned",
            resource_type="alert",
            resource_id=str(alert_id),
            details={
                "previous_user_id": previous_user_id,
                "assigned_user_id": assigned_user.id,
            },
            source_ip=request.client.host if request.client else None,
        )
    )

    database.commit()
    database.refresh(assignment)

    return assignment


@router.get(
    "/{alert_id}/assignment",
    response_model=AlertAssignmentResponse,
)
def get_alert_assignment(
    alert_id: int,
    current_user: CurrentUser,
    database: DatabaseSession,
):
    assignment = database.scalar(
        select(AlertAssignment).where(
            AlertAssignment.alert_id == alert_id
        )
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert is not assigned.",
        )

    return assignment

@router.post(
    "/{alert_id}/notes",
    response_model=AlertNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_alert_note(
    alert_id: int,
    note_data: AlertNoteCreate,
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

    note = AlertNote(
        alert_id=alert_id,
        author_user_id=current_user.id,
        body=note_data.body.strip(),
    )

    database.add(note)
    database.flush()

    database.add(
        AuditLog(
            user_id=current_user.id,
            action="alert.note_added",
            resource_type="alert",
            resource_id=str(alert_id),
            details={
                "note_id": note.id,
            },
            source_ip=request.client.host if request.client else None,
        )
    )

    database.commit()
    database.refresh(note)

    return note


@router.get(
    "/{alert_id}/notes",
    response_model=list[AlertNoteResponse],
)
def list_alert_notes(
    alert_id: int,
    current_user: CurrentUser,
    database: DatabaseSession,
):
    alert = database.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )

    notes = database.scalars(
        select(AlertNote)
        .where(AlertNote.alert_id == alert_id)
        .order_by(AlertNote.created_at.asc())
    ).all()

    return list(notes)