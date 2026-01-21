import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_from_directory
from flask_jwt_extended import current_user, jwt_required

from backend import db
from backend.app_config import (
    TELCORAIN_INT_PATH,
    TELCORAIN_INT_PATH_JSON,
    TELCORAIN_MAX_CALCS,
    TELCORAIN_SUM_PATH,
    TELCORAIN_SUM_PATH_JSON,
)
from backend.db_models import CalcStatus, Calculation
from backend.tasks import run_rain_calculation
from backend.utils import extract_timestamp_and_score, parse_isoformat_z

historic = Blueprint("historic", __name__)

INTENSITIES_BASE_DIR = Path("./intensities").resolve()
SUM_BASE_DIR = Path("./sum").resolve()


def _user_base_dir(user_id: int, image_type: str) -> Path:
    if image_type == "intensity":
        return (INTENSITIES_BASE_DIR / str(user_id)).resolve()
    else:
        return (SUM_BASE_DIR / str(user_id)).resolve()


def _safe_calc_dir_for_user(user_id: int, calc_name: str, image_type: str) -> Path:
    """
    Returns a resolved path like <base>/<user_id>/<calc_name> and guarantees it
    cannot escape <base>/<user_id>/ (prevents path traversal / weird names).
    """
    user_dir = _user_base_dir(user_id, image_type)
    calc_dir = (user_dir / calc_name).resolve()

    # Require calc_dir to be within user_dir (strict prefix with path separator)
    user_prefix = str(user_dir) + os.sep
    if not str(calc_dir).startswith(user_prefix):
        abort(400, "Invalid calculation path")

    return calc_dir


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
    )

    db.session.add(calc)

    db.session.commit()

    cfg = {
        # time settings
        "time": {
            "step": data["step"],
            "output_step": data["output_step"],
            "start": start,
            "end": end,
        },
        # CML filtering
        "cml": {
            "min_length": data["min_length"],
            "max_length": data["max_length"],
            # manual filtration using the csv in the telcorain repo
            "exclude_cmls": data["exclude_cmls"],
        },
        # user info for folder names and link selection (list of IDs)
        "user_info": {
            "links_id": payload["links_id"],
            "output_dir_int": f"{TELCORAIN_INT_PATH}/{user_id}/{data['name']}",
            "output_dir_int_json": f"{TELCORAIN_INT_PATH_JSON}/{user_id}/{data['name']}",
            "output_dir_sum": f"{TELCORAIN_SUM_PATH}/{user_id}/{data['name']}",
            "output_dir_sum_json": f"{TELCORAIN_SUM_PATH_JSON}/{user_id}/{data['name']}",
        },
        "wet_dry": {
            "is_mlp_enabled": data["is_mlp_enabled"],
            "rolling_hours": data["rolling_hours"],
            "rolling_values": data["rolling_values"],
            "wet_dry_deviation": data["wet_dry_deviation"],
            "baseline_samples": data["baseline_samples"],
        },
        "interp": {
            "idw_power": data["idw_power"],
            "idw_near": data["idw_near"],
            "idw_dist_m": data["idw_dist_m"],
        },
        "rendering": {
            "is_crop_enabled": data["is_crop_enabled"],
        },
    }

    # send to background worker via celery
    run_rain_calculation.delay(calc.id, cfg)

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

    # prevent deleting active jobs
    if calc.status in (CalcStatus.PENDING, CalcStatus.RUNNING):
        return jsonify({"error": "Cannot delete an active calculation"}), 400

    # Build folder path safely from DB value (calc.name)
    calc_dir_int = _safe_calc_dir_for_user(user_id, calc.name, "intensity")
    # Remove folder with images (if present)
    if calc_dir_int.exists() and calc_dir_int.is_dir():
        shutil.rmtree(calc_dir_int)
    # Build folder path safely from DB value (calc.name)
    calc_dir_sum = _safe_calc_dir_for_user(user_id, calc.name, "sum")
    # Remove folder with images (if present)
    if calc_dir_sum.exists() and calc_dir_sum.is_dir():
        shutil.rmtree(calc_dir_sum)

    db.session.delete(calc)
    db.session.commit()

    return jsonify({"message": "Calculation deleted", "calculation_id": calc_id}), 200


@historic.route("/api/intensities/<string:calc_name>/list", methods=["GET"])
@jwt_required()
def historic_intensity_list(calc_name: str):
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

    if start_dt > end_dt:
        abort(400, "'start' must be <= 'end'")

    # Lookup calculation by name + user_id (authz)
    calc = Calculation.query.filter_by(user_id=user_id, name=calc_name).first()
    if not calc:
        abort(404, f"No calculation found for name={calc_name}")

    # Use DB calc.name as truth for path
    calc_dir = _safe_calc_dir_for_user(user_id, calc.name, "intensity")
    if not calc_dir.exists() or not calc_dir.is_dir():
        abort(404, f"No files found for calculation '{calc.name}'")

    results = []
    for file_path in sorted(calc_dir.glob("*.png")):
        try:
            ts, score = extract_timestamp_and_score(file_path.name)
        except ValueError:
            continue

        if start_dt <= ts <= end_dt:
            results.append(
                {
                    "timestamp": ts.isoformat(),
                    # NOTE: matches the route below (has /api)
                    "url": f"/intensities/{user_id}/{calc.name}/{file_path.name}",
                    "rain_score": score,
                }
            )

    return jsonify(results), 200


@historic.route("/api/intensities/<int:user_id>/<string:calc_name>/<path:filename>")
@jwt_required()
def historic_intensity_file(user_id: int, calc_name: str, filename: str):
    # IDOR prevention: only allow requesting your own user_id
    if user_id != current_user.id:
        abort(403)

    # Ensure calc_name actually belongs to this user (prevents probing disk)
    calc = Calculation.query.filter_by(user_id=user_id, name=calc_name).first()
    if not calc:
        abort(404)

    # Build base calc dir safely from DB calc.name
    calc_dir = _safe_calc_dir_for_user(user_id, calc.name, "intensity")

    # Resolve requested file path and ensure it stays inside calc_dir
    requested_path = (calc_dir / filename).resolve()
    calc_prefix = str(calc_dir) + os.sep
    if not str(requested_path).startswith(calc_prefix):
        abort(403)

    if not requested_path.exists() or not requested_path.is_file():
        abort(404)

    # (optional) enforce PNG only
    if requested_path.suffix.lower() != ".png":
        abort(404)

    return send_from_directory(
        directory=str(requested_path.parent),
        path=requested_path.name,
        mimetype="image/png",
    )


# SUM list
@historic.route("/api/sum/<string:calc_name>/list", methods=["GET"])
@jwt_required()
def historic_list(calc_name: str):
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

    if start_dt > end_dt:
        abort(400, "'start' must be <= 'end'")

    # Lookup calculation by name + user_id (authz)
    calc = Calculation.query.filter_by(user_id=user_id, name=calc_name).first()
    if not calc:
        abort(404, f"No calculation found for name={calc_name}")

    # Use DB calc.name as truth for path
    calc_dir = _safe_calc_dir_for_user(user_id, calc.name, "sum")
    if not calc_dir.exists() or not calc_dir.is_dir():
        abort(404, f"No files found for calculation '{calc.name}'")

    results = []
    for file_path in sorted(calc_dir.glob("*.png")):
        try:
            ts, score = extract_timestamp_and_score(file_path.name)
        except ValueError:
            continue

        if start_dt <= ts <= end_dt:
            results.append(
                {
                    "timestamp": ts.isoformat(),
                    # NOTE: matches the route below (has /api)
                    "url": f"/sum/{user_id}/{calc.name}/{file_path.name}",
                    "rain_score": score,
                }
            )

    return jsonify(results), 200


@historic.route("/api/sum/<int:user_id>/<string:calc_name>/<path:filename>")
@jwt_required()
def historic_sum_file(user_id: int, calc_name: str, filename: str):
    # IDOR prevention: only allow requesting your own user_id
    if user_id != current_user.id:
        abort(403)

    # Ensure calc_name actually belongs to this user (prevents probing disk)
    calc = Calculation.query.filter_by(user_id=user_id, name=calc_name).first()
    if not calc:
        abort(404)

    # Build base calc dir safely from DB calc.name
    calc_dir = _safe_calc_dir_for_user(user_id, calc.name, "sum")

    # Resolve requested file path and ensure it stays inside calc_dir
    requested_path = (calc_dir / filename).resolve()
    calc_prefix = str(calc_dir) + os.sep
    if not str(requested_path).startswith(calc_prefix):
        abort(403)

    if not requested_path.exists() or not requested_path.is_file():
        abort(404)

    # (optional) enforce PNG only
    if requested_path.suffix.lower() != ".png":
        abort(404)

    return send_from_directory(
        directory=str(requested_path.parent),
        path=requested_path.name,
        mimetype="image/png",
    )
