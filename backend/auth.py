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

from backend import bcrypt, jwt
from backend.auth_utils import (
    SESSION_EXP_CLAIM,
    SESSION_ID_CLAIM,
    create_session_access_token,
    get_session_expires_at,
    is_session_expired,
    utc_now,
)
from backend.db_models import AuthBlocklist, User

auth = Blueprint("auth", __name__)


def revoke_token(*, jwt_data: dict, reason: str, revoke_session: bool = False) -> None:
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
        from backend import db

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
            "username": current_user.username,
            "org": current_user.org,
            "link_access_type": current_user.link_access_type.value,
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
