from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegistration(BaseModel):
    device_id: str = Field(min_length=3, max_length=100)
    hostname: str = Field(min_length=1, max_length=100)
    operating_system: str = Field(min_length=1, max_length=200)
    ip_address: str = Field(min_length=3, max_length=45)
    agent_version: str = Field(default="0.1.0", max_length=20)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    hostname: str
    operating_system: str
    ip_address: str
    agent_version: str
    status: str
    first_seen: datetime
    last_seen: datetime

class SecurityEventCreate(BaseModel):
    device_id: str = Field(min_length=3, max_length=100)
    windows_event_id: int = Field(ge=0)
    record_id: int | None = Field(default=None, ge=0)
    log_name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=200)
    level: str = Field(min_length=1, max_length=50)
    message: str = Field(min_length=1)
    occurred_at: datetime
    raw_data: dict | None = None


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    windows_event_id: int
    record_id: int | None
    log_name: str
    provider: str
    level: str
    message: str
    occurred_at: datetime
    received_at: datetime
    raw_data: dict | None

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    security_event_id: int
    rule_id: str
    title: str
    description: str
    severity: str
    status: str
    created_at: datetime

class AlertStatusUpdate(BaseModel):
    status: Literal[
        "open",
        "investigating",
        "resolved",
        "dismissed",
    ]

class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=100,
    )

    password: str = Field(
        min_length=12,
        max_length=128,
    )


class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )

    password: str = Field(
        min_length=12,
        max_length=128,
    )

    role: Literal[
        "analyst",
        "admin",
    ] = "analyst"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict | None
    source_ip: str | None
    created_at: datetime

class AlertAssignmentCreate(BaseModel):
    assigned_user_id: int = Field(gt=0)


class AlertAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    assigned_user_id: int
    assigned_by_user_id: int
    assigned_at: datetime
    updated_at: datetime


class AlertNoteCreate(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=4000,
    )


class AlertNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    author_user_id: int
    body: str
    created_at: datetime