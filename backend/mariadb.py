from math import atan2, cos, radians, sin, sqrt

from flask import Blueprint, jsonify
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend import db
from backend.db_models import LinkAccessType, User
from backend.db_models_cml import Link, Technology
from backend.db_models_ws import WeatherStation, WeatherStationMeasurement10M

mariadb = Blueprint("mariadb", __name__)


@mariadb.route("/api/weather-stations", methods=["GET"])
def get_weather_stations():
    query = select(WeatherStation).options(
        selectinload(WeatherStation.measurements_10m).selectinload(
            WeatherStationMeasurement10M.measurement_10m
        )
    )
    stations = db.session.execute(query).scalars().all()

    return jsonify(
        [
            {
                "id": station.id,
                "wsi": station.wsi,
                "gh_id": station.gh_id,
                "full_name": station.full_name,
                "X": station.X,
                "Y": station.Y,
                "elevation": station.elevation,
                "measurements": [
                    m.measurement_10m.abbreviation
                    for m in station.measurements_10m
                    if m.measurement_10m
                ],
            }
            for station in stations
            if any(m.measurement_10m for m in station.measurements_10m)
        ]
    )


def haversine_meters(lat1, lon1, lat2, lon2):
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = (
        sin(dLat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = 6371000 * c
    return round(distance, 2)


def midpoint_xy(x1, y1, x2, y2):
    return round((x1 + x2) / 2, 7), round((y1 + y2) / 2, 7)


@mariadb.route("/api/links", methods=["GET"])
@jwt_required(optional=True)
def links():
    user: User | None = current_user

    if not user:
        return jsonify([])

    # Logged in user with full link access -> return full link data
    if user.link_access and user.link_access_type == LinkAccessType.FULL:
        query = (
            select(Link)
            .options(
                selectinload(Link.site_A),
                selectinload(Link.site_B),
                selectinload(Link.technology).selectinload(Technology.influx_mapping),
            )
            .join(Link.technology)
            .where(Technology.influx_mapping_id.is_not(None))
        )

        links = db.session.execute(query).scalars().all()

        return jsonify(
            [
                {
                    "id": link.id,
                    "ip_address_A": link.ip_address_A,
                    "ip_address_B": link.ip_address_B,
                    "site_A": {
                        "name": link.site_A.address or f"Site {link.site_A.id}",
                        "x": link.site_A.x_coordinate,
                        "y": link.site_A.y_coordinate,
                        "altitude": link.site_A.altitude,
                    },
                    "site_B": {
                        "name": link.site_B.address or f"Site {link.site_B.id}",
                        "x": link.site_B.x_coordinate,
                        "y": link.site_B.y_coordinate,
                        "altitude": link.site_B.altitude,
                    },
                    "technology": link.technology.name
                    or f"Technology {link.technology.id}",
                    "influx_mapping": link.technology.influx_mapping.measurement,
                    "polarization": link.polarization,
                    "frequency_A": link.frequency_A,
                    "frequency_B": link.frequency_B,
                    "length": haversine_meters(
                        link.site_A.y_coordinate,
                        link.site_A.x_coordinate,
                        link.site_B.y_coordinate,
                        link.site_B.x_coordinate,
                    ),
                    "center_x": round(
                        (link.site_A.x_coordinate + link.site_B.x_coordinate) / 2, 7
                    ),
                    "center_y": round(
                        (link.site_A.y_coordinate + link.site_B.y_coordinate) / 2, 7
                    ),
                }
                for link in links
            ]
        )

    # Logged in users without full link access -> return only id + midpoint
    query = (
        select(Link)
        .options(
            selectinload(Link.site_A),
            selectinload(Link.site_B),
        )
        .join(Link.technology)
        .where(Technology.influx_mapping_id.is_not(None))
    )

    links = db.session.execute(query).scalars().all()

    return jsonify(
        [
            {
                "id": link.id,
                "center_x": round(
                    (link.site_A.x_coordinate + link.site_B.x_coordinate) / 2, 7
                ),
                "center_y": round(
                    (link.site_A.y_coordinate + link.site_B.y_coordinate) / 2, 7
                ),
            }
            for link in links
        ]
    )
