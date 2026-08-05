import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt.exceptions import InvalidTokenError
from pwdlib.hashers.bcrypt import BcryptHasher
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from backend.database import get_database
from backend.models import User


SESSION_COOKIE_NAME = "watchtower_session"
JWT_ALGORITHM = "HS256"
SESSION_LENGTH_MINUTES = 60

password_hasher = PasswordHash((BcryptHasher(),))

DatabaseSession = Annotated[Session, Depends(get_database)]


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    stored_password_hash: str,
) -> bool:
    return password_hasher.verify(
        plain_password,
        stored_password_hash,
    )


def get_jwt_secret() -> str:
    jwt_secret = os.getenv("WATCHTOWER_JWT_SECRET")

    if not jwt_secret:
        raise RuntimeError(
            "WATCHTOWER_JWT_SECRET is not configured."
        )

    return jwt_secret


def create_session_token(user: User) -> str:
    current_time = datetime.now(timezone.utc)
    expires_at = current_time + timedelta(
        minutes=SESSION_LENGTH_MINUTES
    )

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": current_time,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
    )


def get_current_user(
    request: Request,
    database: DatabaseSession,
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise authentication_error()

    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )

        user_id = int(payload["sub"])
    except (
        InvalidTokenError,
        KeyError,
        TypeError,
        ValueError,
    ):
        raise authentication_error()

    user = database.get(User, user_id)

    if user is None or not user.is_active:
        raise authentication_error()

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )

    return current_user


AdminUser = Annotated[
    User,
    Depends(require_admin),
]