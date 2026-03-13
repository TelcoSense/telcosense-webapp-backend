from datetime import timedelta

from flask import Flask, request
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from backend.app_config import Config
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

            if request.path == "/api/login-check":
                return response

            identity = get_jwt_identity()

            # no authenticated identity present
            if identity is None:
                return response

            access_token = create_access_token(
                identity=identity,
                expires_delta=timedelta(minutes=30),
            )
            set_access_cookies(response, access_token)

        except (RuntimeError, KeyError):
            pass

        return response

    return app, celery
