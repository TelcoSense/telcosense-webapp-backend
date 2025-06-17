from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend import db


class User(db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    org: Mapped[str] = mapped_column(String(10), nullable=False, default="BUT")
    link_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# class HistoricCalculation(db.Model):
#     __tablename__ = "historic_calculations"
