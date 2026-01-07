from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    current_user,
    get_jwt,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)

from backend import bcrypt, jwt
from backend.db_models import User

auth = Blueprint("auth", __name__)


@jwt.user_identity_loader
def user_identity_lookup(user):
    return str(user.id)


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.filter_by(id=identity).one_or_none()


@auth.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"message": "Missing credentials"}), 400
    user = User.query.filter_by(username=username).one_or_none()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({"message": "Invalid credentials"}), 401
    access_token = create_access_token(identity=user)
    response = jsonify({"message": "Login successful"})
    set_access_cookies(response, access_token)
    return response


@auth.route("/api/login-check", methods=["GET"])
@jwt_required()
def login_check():
    jwt_data = get_jwt()
    return jsonify(
        {
            "valid": True,
            "username": current_user.username,
            "org": current_user.org,
            "exp": jwt_data["exp"],
        }
    )


@auth.route("/api/token-info", methods=["GET"])
@jwt_required()
def token_info():
    jwt_data = get_jwt()
    return jsonify({"exp": jwt_data["exp"]})


@auth.route("/api/logout", methods=["POST"])
def logout():
    response = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(response)
    return response
