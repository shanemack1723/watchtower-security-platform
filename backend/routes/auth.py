from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_security import (
    AdminUser,
    CurrentUser,
    SESSION_COOKIE_NAME,
    SESSION_LENGTH_MINUTES,
    create_session_token,
    hash_password,
    verify_password,
)
from backend.database import get_database
from backend.models import AuditLog, User
from backend.schemas import LoginRequest, UserCreate, UserResponse


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


DatabaseSession = Annotated[Session, Depends(get_database)]


def get_source_ip(request: Request) -> str | None:
    if request.client is None:
        return None

    return request.client.host


@router.post(
    "/login",
    response_model=UserResponse,
)
def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    database: DatabaseSession,
):
    normalized_username = login_data.username.lower()

    user = database.scalar(
        select(User).where(
            User.username == normalized_username
        )
    )

    if (
        user is None
        or not user.is_active
        or not verify_password(
            login_data.password,
            user.password_hash,
        )
    ):
        database.add(
            AuditLog(
                user_id=user.id if user else None,
                action="authentication.failed",
                resource_type="session",
                details={
                    "username": normalized_username,
                },
                source_ip=get_source_ip(request),
            )
        )
        database.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    user.last_login_at = datetime.now(timezone.utc)

    database.add(
        AuditLog(
            user_id=user.id,
            action="authentication.succeeded",
            resource_type="session",
            resource_id=str(user.id),
            details={
                "username": user.username,
                "role": user.role,
            },
            source_ip=get_source_ip(request),
        )
    )

    database.commit()
    database.refresh(user)

    session_token = create_session_token(user)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_LENGTH_MINUTES * 60,
        httponly=True,
        secure=False,
        samesite="strict",
        path="/",
    )

    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    database: DatabaseSession,
):
    database.add(
        AuditLog(
            user_id=current_user.id,
            action="authentication.logout",
            resource_type="session",
            resource_id=str(current_user.id),
            source_ip=get_source_ip(request),
        )
    )
    database.commit()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_authenticated_user(
    current_user: CurrentUser,
):
    return current_user


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    request: Request,
    admin_user: AdminUser,
    database: DatabaseSession,
):
    normalized_username = user_data.username.lower()

    existing_user = database.scalar(
        select(User).where(
            User.username == normalized_username
        )
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username already exists.",
        )

    new_user = User(
        username=normalized_username,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
        is_active=True,
    )

    database.add(new_user)
    database.flush()

    database.add(
        AuditLog(
            user_id=admin_user.id,
            action="user.created",
            resource_type="user",
            resource_id=str(new_user.id),
            details={
                "username": new_user.username,
                "role": new_user.role,
            },
            source_ip=get_source_ip(request),
        )
    )

    database.commit()
    database.refresh(new_user)

    return new_user


@router.get(
    "/users",
    response_model=list[UserResponse],
)
def list_users(
    admin_user: AdminUser,
    database: DatabaseSession,
):
    users = database.scalars(
        select(User).order_by(User.username)
    ).all()

    return list(users)

@router.get(
    "/analysts",
    response_model=list[UserResponse],
)
def list_active_analysts(
    current_user: CurrentUser,
    database: DatabaseSession,
):
    users = database.scalars(
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.username)
    ).all()

    return list(users)