from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend import db


class WeatherStationMeasurement10M(db.Model):
    __bind_key__ = "ws"
    __tablename__ = "weather_station_measurements_10m"

    weather_station_id: Mapped[int] = mapped_column(
        ForeignKey("weather_stations.id"), primary_key=True
    )
    measurement_10m_id: Mapped[int] = mapped_column(
        ForeignKey("measurements_10m.id"), primary_key=True
    )

    weather_station: Mapped["WeatherStation"] = relationship(
        back_populates="measurements_10m"
    )

    measurement_10m: Mapped["Measurement10M"] = relationship(
        back_populates="weather_stations"
    )


class WeatherStation(db.Model):
    __bind_key__ = "ws"
    __tablename__ = "weather_stations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wsi: Mapped[str] = mapped_column(String(255), nullable=False)
    gh_id: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    X: Mapped[float] = mapped_column(Float, nullable=False)
    Y: Mapped[float] = mapped_column(Float, nullable=False)
    elevation: Mapped[float] = mapped_column(Float, nullable=False)

    measurements_10m: Mapped[list["WeatherStationMeasurement10M"]] = relationship(
        back_populates="weather_station", cascade="all, delete-orphan"
    )


class Measurement10M(db.Model):
    __bind_key__ = "ws"
    __tablename__ = "measurements_10m"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    abbreviation: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(255), nullable=False)

    weather_stations: Mapped[list["WeatherStationMeasurement10M"]] = relationship(
        back_populates="measurement_10m", cascade="all, delete-orphan"
    )
