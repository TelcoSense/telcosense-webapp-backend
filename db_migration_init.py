from flask_migrate import init

from backend import create_app

app = create_app()

with app.app_context():
    init("./migrations")
