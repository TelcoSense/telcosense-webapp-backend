from datetime import datetime
from typing import List, Optional

from sqlalchemy import Enum, Float, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend import db


class Site(db.Model):
    __bind_key__ = "cml"
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column("ID", primary_key=True, autoincrement=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(Text)
    x_coordinate: Mapped[float] = mapped_column("X_coordinate", default=0)
    y_coordinate: Mapped[float] = mapped_column("Y_coordinate", default=0)
    x_dummy_coordinate: Mapped[float] = mapped_column("X_dummy_coordinate", default=0)
    y_dummy_coordinate: Mapped[float] = mapped_column("Y_dummy_coordinate", default=0)
    altitude: Mapped[Optional[float]] = mapped_column()
    height_above_terrain: Mapped[Optional[float]] = mapped_column()

    links_A: Mapped[List["Link"]] = relationship(
        back_populates="site_A", foreign_keys="[Link.site_A_id]"
    )
    links_B: Mapped[List["Link"]] = relationship(
        back_populates="site_B", foreign_keys="[Link.site_B_id]"
    )


class TechnologiesInfluxMapping(db.Model):
    __bind_key__ = "cml"
    __tablename__ = "technologies_influx_mapping"

    id: Mapped[int] = mapped_column("ID", primary_key=True, autoincrement=True)
    measurement: Mapped[str] = mapped_column(Text, nullable=False)
    ip_tag: Mapped[str] = mapped_column("IP_tag", Text, nullable=False)
    rsl_field: Mapped[Optional[str]] = mapped_column(Text)
    tsl_field: Mapped[Optional[str]] = mapped_column(Text)
    temperature_field: Mapped[Optional[str]] = mapped_column(Text)

    technologies: Mapped[List["Technology"]] = relationship(
        back_populates="influx_mapping"
    )


class Technology(db.Model):
    __bind_key__ = "cml"
    __tablename__ = "technologies"

    id: Mapped[int] = mapped_column("ID", primary_key=True, autoincrement=True)
    isp_id: Mapped[int] = mapped_column("ISP_ID", default=0)
    vendor_id: Mapped[int] = mapped_column("vendor_ID", default=0)
    name: Mapped[Optional[str]] = mapped_column(Text)
    atpc: Mapped[Optional[bool]] = mapped_column("ATPC", default=True)
    influx_mapping_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("technologies_influx_mapping.ID")
    )

    influx_mapping: Mapped[Optional["TechnologiesInfluxMapping"]] = relationship(
        back_populates="technologies"
    )
    links: Mapped[List["Link"]] = relationship(back_populates="technology")


class Link(db.Model):
    __bind_key__ = "cml"
    __tablename__ = "links"

    id: Mapped[int] = mapped_column("ID", primary_key=True, autoincrement=True)
    isp_id: Mapped[Optional[int]] = mapped_column("ISP_ID")
    is_active: Mapped[bool] = mapped_column(default=True)
    ip_address_A: Mapped[Optional[str]] = mapped_column("IP_address_A", String(15))
    ip_address_B: Mapped[Optional[str]] = mapped_column("IP_address_B", String(15))
    site_A_id: Mapped[int] = mapped_column("site_A", ForeignKey("sites.ID"))
    site_B_id: Mapped[int] = mapped_column("site_B", ForeignKey("sites.ID"))
    frequency_A: Mapped[int] = mapped_column(default=10500)
    frequency_B: Mapped[int] = mapped_column(default=10500)
    polarization: Mapped[str] = mapped_column(
        Enum("V", "H", "X", name="polarization_enum"), default="V"
    )
    distance: Mapped[Optional[float]] = mapped_column()
    azimuth_A: Mapped[Optional[float]] = mapped_column()
    azimuth_B: Mapped[Optional[float]] = mapped_column()
    import_time: Mapped[datetime] = mapped_column(
        server_default=text("utc_timestamp()")
    )
    modify_time: Mapped[Optional[datetime]] = mapped_column()
    serial_A: Mapped[Optional[str]] = mapped_column(Text)
    serial_B: Mapped[Optional[str]] = mapped_column(Text)

    site_A: Mapped["Site"] = relationship(
        back_populates="links_A", foreign_keys=[site_A_id]
    )
    site_B: Mapped["Site"] = relationship(
        back_populates="links_B", foreign_keys=[site_B_id]
    )
    technology_id: Mapped[int] = mapped_column(
        "technology", ForeignKey("technologies.ID")
    )
    technology: Mapped["Technology"] = relationship(back_populates="links")
