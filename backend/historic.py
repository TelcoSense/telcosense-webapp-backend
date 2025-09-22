import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from backend import db
from backend.app_config import TELCORAIN_OUT_PATH
from backend.db_models import CalcStatus, Calculation
from backend.tasks import run_rain_calculation

historic = Blueprint("historic", __name__)


@historic.route("/api/start-rain-calculation", methods=["POST"])
@jwt_required()
def start_rain_calculation():
    payload = request.get_json()
    user_id = current_user.id

    start = payload["start"]
    end = payload["end"]
    data = payload["data"]

    # enforce limit
    active_jobs = (
        Calculation.query.filter_by(user_id=user_id)
        .filter(Calculation.status.in_([CalcStatus.PENDING, CalcStatus.RUNNING]))
        .count()
    )

    if active_jobs >= 3:
        return jsonify({"error": "You already have 3 active calculations"}), 400

    # create calc record
    calc = Calculation(
        user_id=user_id,
        name=data["name"],
        status=CalcStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )

    db.session.add(calc)
    db.session.commit()

    cp = {
        # time setting (probably dont change step and output_step)
        "time": {
            "step": 10,
            "output_step": 10,
            "start": start,
            "end": end,
        },
        # CML filtering
        "cml": {
            "min_length": data["min_length"],
            "max_length": data["max_length"],
        },
        # db settings for historic calculation
        "historic": {
            "skip_influx": True,
        },
        "wet_dry": {
            "is_mlp_enabled": data["is_mlp_enabled"],
            "cnn_model": "ours",
            "cnn_model_name": "cnn_v22_ds_cz_param_2025-05-15_22;01",
            "rolling_hours": data["rolling_hours"],
            "rolling_values": data["rolling_values"],
            "wet_dry_deviation": data["wet_dry_deviation"],
            "baseline_samples": data["baseline_samples"],
            "is_window_centered": False,
        },
        "interp": {
            "interp_res": data["interp_res"],
            "idw_power": data["idw_power"],
            "idw_near": data["idw_near"],
            "idw_dist": data["idw_dist"],
        },
        "limits": {
            "x_min": data["x_min"],
            "x_max": data["x_max"],
            "y_min": data["y_min"],
            "y_max": data["y_max"],
        },
        # user info for folder names and link selection (list of IDs)
        "user_info": {
            "folder_name": data["name"],
            "links_id": payload["links_id"],
            "output_dir": f"{TELCORAIN_OUT_PATH}/{user_id}/{data["name"]}",
        },
        "rendering": {
            "is_crop_enabled": data["is_crop_enabled"],
            "geojson_file": "czechia.json",
            "map": "plain_czechia.png",
        },
    }

    # send to background worker via celery
    run_rain_calculation.delay(calc.id, cp)

    return jsonify({"message": "Calculation started", "calculation_id": calc.id})


@historic.route("/api/rain-calculations", methods=["GET"])
@jwt_required()
def list_rain_calculations():
    user_id = current_user.id
    calcs = (
        Calculation.query.filter_by(user_id=user_id)
        .order_by(Calculation.created_at.desc())
        .all()
    )

    return jsonify(
        [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status.value,
                "result": c.result,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in calcs
        ]
    )
