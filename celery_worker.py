from backend import create_app
from backend.tasks import celery

app = create_app()
app.app_context().push()
