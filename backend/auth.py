import secrets

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    current_user,
    get_jwt,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
from flask_jwt_extended.exceptions import JWTExtendedException
from sqlalchemy import or_

from backend import bcrypt, db, jwt
from backend.auth_utils import (
    SESSION_EXP_CLAIM,
    SESSION_ID_CLAIM,
    create_session_access_token,
    get_session_expires_at,
    is_session_expired,
    utc_now,
)
from backend.db_models import AuthBlocklist, LinkAccessType, User

auth = Blueprint("auth", __name__)


def prune_expired_blocklist() -> int:
    return (
        db.session.query(AuthBlocklist)
        .filter(AuthBlocklist.expires_at < utc_now())
        .delete(synchronize_session=False)
    )


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "org": user.org,
        "link_access": user.link_access,
        "link_access_type": user.link_access_type.value,
        "calculation_access": user.calculation_access,
        "is_admin": user.is_admin,
    }


def admin_forbidden_response():
    return jsonify({"message": "Admin access required", "code": "admin_required"}), 403


def ensure_admin():
    if current_user is None or not current_user.is_admin:
        return admin_forbidden_response()
    return None


def parse_link_access_type(value: object) -> LinkAccessType:
    if not isinstance(value, str):
        raise ValueError("Invalid link_access_type")

    normalized = value.lower()
    try:
        return LinkAccessType(normalized)
    except ValueError as exc:
        raise ValueError("Invalid link_access_type") from exc


def require_bool(data: dict, field: str, default: bool | None = None) -> bool:
    if field not in data:
        if default is None:
            raise ValueError(f"Missing {field}")
        return default

    value = data[field]
    if not isinstance(value, bool):
        raise ValueError(f"Invalid {field}")
    return value


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode("utf-8")


def generate_password() -> str:
    return secrets.token_urlsafe(10)


def revoke_token(*, jwt_data: dict, reason: str, revoke_session: bool = False) -> None:
    prune_expired_blocklist()
    expires_at = get_session_expires_at(jwt_data) or utc_now()
    user_id = jwt_data.get("sub")
    block_entry = AuthBlocklist(
        jti=None if revoke_session else jwt_data["jti"],
        session_id=jwt_data.get(SESSION_ID_CLAIM),
        user_id=int(user_id) if user_id is not None else None,
        token_type=jwt_data.get("type", "access"),
        revoked_reason=reason,
        expires_at=expires_at,
    )
    if not revoke_session:
        block_entry.session_id = None

    existing = None
    if revoke_session:
        existing = AuthBlocklist.query.filter_by(
            session_id=jwt_data.get(SESSION_ID_CLAIM), jti=None
        ).one_or_none()
    elif jwt_data.get("jti"):
        existing = AuthBlocklist.query.filter_by(jti=jwt_data["jti"]).one_or_none()

    if existing is None:
        db.session.add(block_entry)

    db.session.commit()


@jwt.user_identity_loader
def user_identity_lookup(user):
    if user is None:
        return None
    if isinstance(user, (str, int)):
        return str(user)
    return str(user.id)


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.filter_by(id=identity).one_or_none()


@jwt.token_in_blocklist_loader
def token_in_blocklist_callback(_jwt_header, jwt_data):
    if is_session_expired(jwt_data):
        return True

    jti = jwt_data.get("jti")
    session_id = jwt_data.get(SESSION_ID_CLAIM)

    blocked = AuthBlocklist.query.filter(
        AuthBlocklist.expires_at >= utc_now(),
        or_(
            AuthBlocklist.jti == jti,
            AuthBlocklist.session_id == session_id,
        ),
    ).first()

    return blocked is not None


@jwt.revoked_token_loader
def revoked_token_callback(_jwt_header, jwt_payload):
    if is_session_expired(jwt_payload):
        return jsonify({"message": "Session expired", "code": "session_expired"}), 401
    return jsonify({"message": "Token revoked", "code": "token_revoked"}), 401


@jwt.expired_token_loader
def expired_token_callback(_jwt_header, _jwt_payload):
    return jsonify({"message": "Token expired", "code": "token_expired"}), 401


@jwt.invalid_token_loader
def invalid_token_callback(reason):
    return jsonify({"message": "Invalid token", "code": "invalid_token", "detail": reason}), 422


@jwt.unauthorized_loader
def unauthorized_callback(reason):
    return jsonify({"message": "Authentication required", "code": "auth_required", "detail": reason}), 401


@jwt.user_lookup_error_loader
def user_lookup_error_callback(_jwt_header, _jwt_payload):
    return jsonify({"message": "User not found", "code": "user_not_found"}), 401


@jwt.needs_fresh_token_loader
def needs_fresh_token_callback(_jwt_header, _jwt_payload):
    return jsonify({"message": "Fresh authentication required", "code": "fresh_token_required"}), 401


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
    access_token, access_exp, session_exp, _session_id = create_session_access_token(
        identity=user,
        fresh=True,
    )
    response = jsonify(
        {
            "message": "Login successful",
            "exp": access_exp,
            "session_exp": session_exp,
        }
    )
    set_access_cookies(response, access_token)
    return response


@auth.route("/api/login-check", methods=["GET"])
@jwt_required()
def login_check():
    jwt_data = get_jwt()
    return jsonify(
        {
            "valid": True,
            "user_id": current_user.id,
            "username": current_user.username,
            "org": current_user.org,
            "link_access_type": current_user.link_access_type.value,
            "is_admin": current_user.is_admin,
            "exp": jwt_data["exp"],
            "session_exp": jwt_data.get(SESSION_EXP_CLAIM),
        }
    )


@auth.route("/api/token-info", methods=["GET"])
@jwt_required()
def token_info():
    jwt_data = get_jwt()
    return jsonify({"exp": jwt_data["exp"], "session_exp": jwt_data.get(SESSION_EXP_CLAIM)})


@auth.route("/api/logout", methods=["POST"])
def logout():
    try:
        verify_jwt_in_request(optional=True)
        jwt_data = get_jwt()
        if jwt_data:
            revoke_token(jwt_data=jwt_data, reason="logout", revoke_session=True)
    except JWTExtendedException:
        pass

    response = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(response)
    return response


@auth.route("/api/admin/users", methods=["GET"])
@jwt_required()
def list_users():
    forbidden = ensure_admin()
    if forbidden is not None:
        return forbidden

    users = User.query.order_by(User.username.asc()).all()
    return jsonify({"users": [serialize_user(user) for user in users]})


@auth.route("/api/admin/users", methods=["POST"])
@jwt_required()
def create_user():
    forbidden = ensure_admin()
    if forbidden is not None:
        return forbidden

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    requested_password = data.get("password")
    org = (data.get("org") or "BUT").strip()
    should_generate_password = data.get("generate_password") is True

    if not username:
        return jsonify({"message": "Username is required"}), 400
    if not org:
        return jsonify({"message": "Org is required"}), 400
    if User.query.filter_by(username=username).one_or_none() is not None:
        return jsonify({"message": "Username already exists"}), 409

    if requested_password is not None and not isinstance(requested_password, str):
        return jsonify({"message": "Invalid password"}), 400

    generated_password = generate_password() if should_generate_password else None
    password = generated_password or requested_password or ""
    if not password:
        return jsonify({"message": "Password is required"}), 400

    try:
        link_access = require_bool(data, "link_access", default=False)
        calculation_access = require_bool(data, "calculation_access", default=False)
        is_admin = require_bool(data, "is_admin", default=False)
        link_access_type = parse_link_access_type(
            data.get("link_access_type", LinkAccessType.FULL.value)
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    user = User(
        username=username,
        password=hash_password(password),
        org=org,
        link_access=link_access,
        link_access_type=link_access_type,
        calculation_access=calculation_access,
        is_admin=is_admin,
    )
    db.session.add(user)
    db.session.commit()

    response = {"message": "User created", "user": serialize_user(user)}
    if generated_password is not None:
        response["generated_password"] = generated_password
    return jsonify(response), 201


@auth.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@jwt_required()
def update_user(user_id: int):
    forbidden = ensure_admin()
    if forbidden is not None:
        return forbidden

    user = User.query.filter_by(id=user_id).one_or_none()
    if user is None:
        return jsonify({"message": "User not found"}), 404

    data = request.get_json(silent=True) or {}

    username = data.get("username")
    if username is not None:
        username = username.strip()
        if not username:
            return jsonify({"message": "Username is required"}), 400
        existing = User.query.filter_by(username=username).one_or_none()
        if existing is not None and existing.id != user.id:
            return jsonify({"message": "Username already exists"}), 409
        user.username = username

    org = data.get("org")
    if org is not None:
        org = org.strip()
        if not org:
            return jsonify({"message": "Org is required"}), 400
        user.org = org

    if "link_access" in data:
        try:
            user.link_access = require_bool(data, "link_access")
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400

    if "calculation_access" in data:
        try:
            user.calculation_access = require_bool(data, "calculation_access")
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400

    if "is_admin" in data:
        try:
            new_is_admin = require_bool(data, "is_admin")
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400

        if user.id == current_user.id and not new_is_admin:
            return jsonify({"message": "You cannot remove your own admin access"}), 400
        user.is_admin = new_is_admin

    if "link_access_type" in data:
        try:
            user.link_access_type = parse_link_access_type(data["link_access_type"])
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400

    password = data.get("password")
    if password is not None:
        if not isinstance(password, str) or not password:
            return jsonify({"message": "Password cannot be empty"}), 400
        user.password = hash_password(password)

    db.session.commit()
    return jsonify({"message": "User updated", "user": serialize_user(user)})


@auth.route("/api/admin/users/<int:user_id>/reset-password", methods=["POST"])
@jwt_required()
def reset_user_password(user_id: int):
    forbidden = ensure_admin()
    if forbidden is not None:
        return forbidden

    user = User.query.filter_by(id=user_id).one_or_none()
    if user is None:
        return jsonify({"message": "User not found"}), 404

    generated_password = generate_password()
    user.password = hash_password(generated_password)
    db.session.commit()

    return jsonify(
        {
            "message": "Password reset",
            "generated_password": generated_password,
            "user": serialize_user(user),
        }
    )


@auth.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id: int):
    forbidden = ensure_admin()
    if forbidden is not None:
        return forbidden

    user = User.query.filter_by(id=user_id).one_or_none()
    if user is None:
        return jsonify({"message": "User not found"}), 404
    if user.id == current_user.id:
        return jsonify({"message": "You cannot delete your own account"}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"})
