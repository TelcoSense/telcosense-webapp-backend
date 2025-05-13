from math import atan2, cos, radians, sin, sqrt

from flask import Blueprint, jsonify
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend import db
from backend.db_models import User
from backend.db_models_cml import Link, Technology
from backend.db_models_ws import WeatherStation

mariadb = Blueprint("mariadb", __name__)


@mariadb.route("/api/weather-stations", methods=["GET"])
@jwt_required()
def get_weather_stations():
    query = select(WeatherStation).join(WeatherStation.measurements_10m).distinct()
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
            }
            for station in stations
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


@mariadb.route("/api/links", methods=["GET"])
@jwt_required()
def links():
    query = (
        select(Link)
        .options(
            selectinload(Link.site_A),
            selectinload(Link.site_B),
            selectinload(Link.technology),
        )
        .join(Link.technology)
        .where(Technology.influx_mapping_id.is_not(None))
    )
    user: User = current_user
    # user must have an access to links
    if user.link_access:
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
                }
                for link in links
            ]
        )
    else:
        # otherwise return empty list
        return jsonify([])
