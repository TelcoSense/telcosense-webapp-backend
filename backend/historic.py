from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required

from backend import db
from backend.db_models import CalcStatus, Calculation
from backend.tasks import run_rain_calculation

historic = Blueprint("historic", __name__)


@historic.route("/start-rain-calculation", methods=["POST"])
@jwt_required()
def start_calculation():
    data = request.get_json()
    user_id = current_user.id
    name = data["name"]

    # enforce limit
    active_jobs = (
        Calculation.query.filter_by(user_id=user_id)
        .filter(Calculation.status.in_([CalcStatus.PENDING, CalcStatus.RUNNING]))
        .count()
    )

    if active_jobs >= 3:
        return jsonify({"error": "You already have 3 active calculations"}), 400

    # create calc record
    calc = Calculation(user_id=user_id, name=name, status=CalcStatus.PENDING)
    db.session.add(calc)
    db.session.commit()

    # send to background worker
    run_rain_calculation.delay(calc.id)

    return jsonify({"message": "Calculation started", "calculation_id": calc.id})


@historic.route("/rain-calculations", methods=["GET"])
@jwt_required()
def list_calculations():
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
