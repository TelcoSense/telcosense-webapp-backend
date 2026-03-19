from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend import db


class LinkAccessType(Enum):
    BASIC = "basic"
    FULL = "full"


class User(db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    org: Mapped[str] = mapped_column(String(10), nullable=False, default="BUT")

    link_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    link_access_type: Mapped[LinkAccessType] = mapped_column(
        SqlEnum(LinkAccessType),
        nullable=False,
        default=LinkAccessType.FULL,
    )
    calculation_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    calculations: Mapped[list["Calculation"]] = relationship(
        "Calculation", back_populates="user", cascade="all, delete-orphan"
    )
    revoked_tokens: Mapped[list["AuthBlocklist"]] = relationship(
        "AuthBlocklist", back_populates="user"
    )


class CalcStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class Calculation(db.Model):
    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CalcStatus] = mapped_column(
        SqlEnum(CalcStatus), nullable=False, default=CalcStatus.PENDING
    )

    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed: Mapped[float | None] = mapped_column(Float, nullable=True)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )

    start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="calculations")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class AuthBlocklist(db.Model):
    __tablename__ = "auth_blocklist"
    __table_args__ = (
        CheckConstraint(
            "jti IS NOT NULL OR session_id IS NOT NULL",
            name="ck_auth_blocklist_target_present",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str | None] = mapped_column(
        String(36), unique=True, nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    token_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="access"
    )
    revoked_reason: Mapped[str] = mapped_column(
        String(255), nullable=False, default="manual"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    user: Mapped["User | None"] = relationship("User", back_populates="revoked_tokens")
