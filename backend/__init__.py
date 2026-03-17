from flask import Flask, request
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from backend.app_config import Config
from backend.auth_utils import (
    SESSION_EXP_CLAIM,
    SESSION_ID_CLAIM,
    create_session_access_token,
    get_session_expires_at,
    should_refresh_token,
    utc_now,
)
from backend.celery_utils import make_celery

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    cors.init_app(
        app,
        supports_credentials=True,
        origins=["http://127.0.0.1:3001"],
        expose_headers=["X-Token-Expires", "X-Session-Expires"],
    )
    # db migrations
    migrate.init_app(app, db)

    celery = make_celery(app)
    celery.set_default()

    from backend.auth import auth
    from backend.chmi_img import chmi_img
    from backend.historic import historic
    from backend.influxdb import influxdb
    from backend.mariadb import mariadb
    from backend.telcosense_img import telcosense_img

    app.register_blueprint(auth)
    app.register_blueprint(chmi_img)
    app.register_blueprint(influxdb)
    app.register_blueprint(mariadb)
    app.register_blueprint(telcosense_img)
    app.register_blueprint(historic)

    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            # raises RuntimeError if there is no valid JWT in request
            jwt_data = get_jwt()

            if request.path in {"/api/login-check", "/api/token-info", "/api/logout"}:
                return response

            identity = get_jwt_identity()

            # no authenticated identity present
            if identity is None:
                return response

            session_expires_at = get_session_expires_at(jwt_data)
            if session_expires_at is None or session_expires_at <= utc_now():
                return response

            response.headers["X-Token-Expires"] = str(jwt_data["exp"])
            response.headers["X-Session-Expires"] = str(jwt_data[SESSION_EXP_CLAIM])

            if not should_refresh_token(jwt_data):
                return response

            from backend.auth import revoke_token

            revoke_token(jwt_data=jwt_data, reason="rotated", revoke_session=False)
            access_token, access_exp, session_exp, _session_id = create_session_access_token(
                identity=identity,
                fresh=False,
                session_id=jwt_data.get(SESSION_ID_CLAIM),
                session_expires_at=session_expires_at,
            )
            set_access_cookies(response, access_token)
            response.headers["X-Token-Expires"] = str(access_exp)
            response.headers["X-Session-Expires"] = str(session_exp)

        except (RuntimeError, KeyError):
            pass

        return response

    return app, celery
