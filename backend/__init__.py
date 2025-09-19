from datetime import timedelta

from flask import Flask, request
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    current_user,
    get_jwt,
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
            # only refresh if the current request had a valid JWT
            _ = get_jwt()  # Will raise RuntimeError if no valid JWT in request
            # skip refresh for specific paths if desired
            if request.path == "/api/login-check":
                return response
            # always refresh: issue a new token that expires in 30 minutes from now
            access_token = create_access_token(
                identity=current_user, expires_delta=timedelta(minutes=30)
            )
            set_access_cookies(response, access_token)
        except (RuntimeError, KeyError):
            # no valid JWT present, skip refreshing
            pass
        return response

    return app, celery
