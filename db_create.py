from sqlalchemy import create_engine, text

from backend.config import DB_NAME, DB_SERVER_CONNECTION_STRING

engine = create_engine(DB_SERVER_CONNECTION_STRING)
with engine.connect() as conn:
    conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME}"))
    conn.execute(
        text(
            f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    )
    conn.commit()
engine.dispose()
