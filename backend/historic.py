import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_from_directory
from flask_jwt_extended import current_user, jwt_required

from backend import db
from backend.app_config import TELCORAIN_MAX_CALCS, TELCORAIN_OUT_PATH
from backend.db_models import CalcStatus, Calculation
from backend.tasks import run_rain_calculation
from backend.utils import extract_timestamp, parse_isoformat_z

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

    if active_jobs >= TELCORAIN_MAX_CALCS:
        return (
            jsonify(
                {"error": f"You already have {TELCORAIN_MAX_CALCS} active calculations"}
            ),
            400,
        )

    print(start)

    # create calc record
    calc = Calculation(
        user_id=user_id,
        name=data["name"],
        status=CalcStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        start=datetime.fromisoformat(start.replace("Z", "+00:00")),
        end=datetime.fromisoformat(end.replace("Z", "+00:00")),
        x_min=data["x_min"],
        x_max=data["x_max"],
        y_min=data["y_min"],
        y_max=data["y_max"],
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
                "elapsed": c.elapsed,
                "shared": c.shared,
                "created_at": c.created_at.replace(tzinfo=timezone.utc).isoformat(),
                "start": c.start.replace(tzinfo=timezone.utc).isoformat(),
                "end": c.end.replace(tzinfo=timezone.utc).isoformat(),
                "x_min": c.x_min,
                "x_max": c.x_max,
                "y_min": c.y_min,
                "y_max": c.y_max,
            }
            for c in calcs
        ]
    )


@historic.route("/api/rain-calculations/<int:calc_id>", methods=["DELETE"])
@jwt_required()
def delete_rain_calculation(calc_id: int):
    user_id = current_user.id
    calc = Calculation.query.filter_by(id=calc_id, user_id=user_id).first()

    if not calc:
        return jsonify({"error": "Calculation not found"}), 404

    # prevent deleting active jobs, enforce here:
    if calc.status in [CalcStatus.PENDING, CalcStatus.RUNNING]:
        return jsonify({"error": "Cannot delete an active calculation"}), 400

    folder_path = f"./telcorain/{user_id}/{calc.name}"
    # also remove folder with images

    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        shutil.rmtree(folder_path)

    db.session.delete(calc)
    db.session.commit()

    return jsonify({"message": "Calculation deleted", "calculation_id": calc_id})


@historic.route("/api/historic/<string:calc_name>/list", methods=["GET"])
@jwt_required()
def historic_list(calc_name):
    user_id = current_user.id

    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if not start_str or not end_str:
        abort(400, "'start' and 'end' query parameters are required (ISO format)")

    try:
        start_dt = parse_isoformat_z(start_str)
        end_dt = parse_isoformat_z(end_str)
    except ValueError:
        abort(400, "Invalid ISO datetime format")

    # Lookup calculation by name + user_id
    calc = Calculation.query.filter_by(user_id=user_id, name=calc_name).first()
    if not calc:
        abort(404, f"No calculation found for name={calc_name}")

    calc_dir = Path(f"./telcorain/{user_id}/{calc_name}")
    if not calc_dir.exists():
        abort(404, f"No files found for calculation '{calc_name}'")

    results = []
    for file_path in sorted(calc_dir.glob("*.png")):
        try:
            ts = extract_timestamp(file_path.name)
            if start_dt <= ts <= end_dt:
                results.append(
                    {
                        "timestamp": ts.isoformat(),
                        "url": f"/historic/{user_id}/{calc_name}/{file_path.name}",
                    }
                )
        except ValueError:
            continue

    return jsonify(results)


@historic.route("/api/historic/<int:user_id>/<string:calc_name>/<path:filename>")
def historic_file(user_id, calc_name, filename):
    base_dir = Path("./telcorain").resolve()
    requested_path = (base_dir / str(user_id) / calc_name / filename).resolve()

    # Prevent path traversal
    if not str(requested_path).startswith(str(base_dir)):
        abort(403)

    if not requested_path.exists():
        abort(404)

    return send_from_directory(
        directory=requested_path.parent, path=requested_path.name, mimetype="image/png"
    )
