from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )
    hostname: Mapped[str] = mapped_column(String(100))
    operating_system: Mapped[str] = mapped_column(String(200))
    ip_address: Mapped[str] = mapped_column(String(45))
    agent_version: Mapped[str] = mapped_column(
        String(20),
        default="0.1.0",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="online",
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"),
        index=True,
    )

    windows_event_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )

    record_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    log_name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(50))

    message: Mapped[str] = mapped_column(Text)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    raw_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

class Alert(Base):
    __tablename__ = "alerts"

    __table_args__ = (
        UniqueConstraint(
            "security_event_id",
            "rule_id",
            name="unique_event_detection_rule",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    security_event_id: Mapped[int] = mapped_column(
        ForeignKey("security_events.id"),
        index=True,
    )

    rule_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)

    severity: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(String(255))

    role: Mapped[str] = mapped_column(
        String(20),
        default="analyst",
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    source_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

class AlertAssignment(Base):
    __tablename__ = "alert_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)

    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id"),
        unique=True,
        index=True,
    )

    assigned_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    assigned_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AlertNote(Base):
    __tablename__ = "alert_notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id"),
        index=True,
    )

    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    body: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

