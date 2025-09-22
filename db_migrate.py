from flask_migrate import migrate

from backend import create_app

app, celery = create_app()

with app.app_context():
    migrate("./migrations")
