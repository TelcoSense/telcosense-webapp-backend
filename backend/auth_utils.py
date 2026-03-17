from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app
from flask_jwt_extended import create_access_token

SESSION_ID_CLAIM = "sid"
SESSION_EXP_CLAIM = "session_exp"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(value: datetime) -> int:
    return int(value.timestamp())


def get_session_expires_at(jwt_data: dict) -> datetime | None:
    session_exp = jwt_data.get(SESSION_EXP_CLAIM)
    if session_exp is None:
        return None
    return datetime.fromtimestamp(session_exp, tz=timezone.utc)


def is_session_expired(jwt_data: dict) -> bool:
    session_expires_at = get_session_expires_at(jwt_data)
    if session_expires_at is None:
        return True
    return session_expires_at <= utc_now()


def should_refresh_token(jwt_data: dict) -> bool:
    exp_timestamp = jwt_data.get("exp")
    if exp_timestamp is None:
        return False

    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    refresh_threshold = current_app.config["JWT_SESSION_REFRESH_THRESHOLD"]
    return expires_at <= utc_now() + refresh_threshold


def create_session_access_token(identity, fresh: bool, session_id: str | None = None, session_expires_at: datetime | None = None) -> tuple[str, int, int, str]:
    now = utc_now()

    if session_id is None:
        session_id = str(uuid4())

    if session_expires_at is None:
        session_expires_at = now + current_app.config["JWT_SESSION_ABSOLUTE_EXPIRES"]

    access_token = create_access_token(
        identity=identity,
        fresh=fresh,
        additional_claims={
            SESSION_ID_CLAIM: session_id,
            SESSION_EXP_CLAIM: to_timestamp(session_expires_at),
        },
    )

    access_expires_at = now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    return access_token, to_timestamp(access_expires_at), to_timestamp(session_expires_at), session_id
