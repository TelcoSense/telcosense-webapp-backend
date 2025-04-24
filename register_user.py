from backend import create_app
from backend.auth import register_user

app = create_app()
with app.app_context():
    register_user("smiklanek")
