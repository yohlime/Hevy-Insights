from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Real
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import delete, insert, select, update

from app.core.database import engine
from app.db.auth import auth_sessions_table
from app.schemas.hevy import HevyUser


@dataclass(frozen=True)
class AuthSession:
    session_id: str
    user_id: str
    access_token: str
    refresh_token: str | None
    expires_at: str | int | float | None
    saved_account_secret: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_db_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def create_auth_session(user: HevyUser, saved_account_secret: str | None) -> str:
    session_id = token_urlsafe(32)
    now = _now_iso()

    with engine.begin() as connection:
        connection.execute(
            insert(auth_sessions_table).values(
                session_id=session_id,
                user_id=user.user_id,
                access_token=user.access_token,
                refresh_token=user.refresh_token,
                expires_at=_optional_db_str(user.expires_at),
                saved_account_secret=saved_account_secret,
                created_at=now,
                updated_at=now,
            )
        )

    return session_id


def get_auth_session(session_id: str) -> AuthSession | None:
    with engine.begin() as connection:
        row = connection.execute(
            select(
                auth_sessions_table.c.session_id,
                auth_sessions_table.c.user_id,
                auth_sessions_table.c.access_token,
                auth_sessions_table.c.refresh_token,
                auth_sessions_table.c.expires_at,
                auth_sessions_table.c.saved_account_secret,
            ).where(auth_sessions_table.c.session_id == session_id)
        ).mappings().one_or_none()

    if not row:
        return None

    return AuthSession(
        session_id=str(row["session_id"]),
        user_id=str(row["user_id"]),
        access_token=str(row["access_token"]),
        refresh_token=_optional_str(row["refresh_token"]),
        expires_at=_optional_str(row["expires_at"]),
        saved_account_secret=_optional_str(row["saved_account_secret"]),
    )


def update_auth_session_tokens(session_id: str, user: HevyUser) -> None:
    with engine.begin() as connection:
        connection.execute(
            update(auth_sessions_table)
            .where(auth_sessions_table.c.session_id == session_id)
            .values(
                access_token=user.access_token,
                refresh_token=user.refresh_token,
                expires_at=_optional_db_str(user.expires_at),
                updated_at=_now_iso(),
            )
        )


def delete_auth_session(session_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(delete(auth_sessions_table).where(auth_sessions_table.c.session_id == session_id))


def is_access_token_expired(expires_at: str | int | float | None) -> bool:
    if not expires_at:
        return False

    try:
        if isinstance(expires_at, Real):
            expiry = datetime.fromtimestamp(float(expires_at), tz=timezone.utc)
        elif expires_at.isdigit():
            expiry = datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
        else:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
    except ValueError:
        return False

    return datetime.now(timezone.utc) >= expiry
