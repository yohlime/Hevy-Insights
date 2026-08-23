from sqlalchemy import Column, String, Table

from app.core.database import metadata


auth_sessions_table = Table(
    "auth_sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("access_token", String, nullable=False),
    Column("refresh_token", String, nullable=True),
    Column("expires_at", String, nullable=True),
    Column("saved_account_secret", String, nullable=True),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)
