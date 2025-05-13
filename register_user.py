import os
import secrets

from backend import bcrypt, create_app, db
from backend.db_models import User


def register_user(username: str, org: str, link_access: bool):
    generated_password = secrets.token_urlsafe(10)
    hashed_password = bcrypt.generate_password_hash(generated_password).decode("utf-8")
    new_user = User(
        username=username, password=hashed_password, org=org, link_access=link_access
    )
    db.session.add(new_user)
    db.session.commit()
    print(generated_password)


app = create_app()
with app.app_context():
    register_user()
