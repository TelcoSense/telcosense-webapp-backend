from flask import Flask
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from backend.app_config import Config

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

    from backend.auth import auth
    from backend.chmi_img import chmi_img
    from backend.influxdb import influxdb
    from backend.mariadb import mariadb
    from backend.telcosense_img import telcosense_img

    app.register_blueprint(auth)
    app.register_blueprint(chmi_img)
    app.register_blueprint(influxdb)
    app.register_blueprint(mariadb)
    app.register_blueprint(telcosense_img)
    return app
