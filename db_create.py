from sqlalchemy import create_engine, text

from backend.app_config import DB_SERVER_CONNECTION_STRING, db_name

engine = create_engine(DB_SERVER_CONNECTION_STRING)
with engine.connect() as conn:
    conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    conn.execute(
        text(
            f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    )
    conn.commit()
engine.dispose()
