from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend import db


class User(db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    org: Mapped[str] = mapped_column(String(10), nullable=False, default="BUT")

    link_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    calculation_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    calculations: Mapped[list["Calculation"]] = relationship(
        "Calculation", back_populates="user", cascade="all, delete-orphan"
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="calculations")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
