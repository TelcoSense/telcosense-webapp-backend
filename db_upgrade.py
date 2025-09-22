from flask_migrate import upgrade

from backend import create_app

app, celery = create_app()

with app.app_context():
    upgrade("./migrations")
