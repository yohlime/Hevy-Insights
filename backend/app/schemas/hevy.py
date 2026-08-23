from pydantic import BaseModel


class HevyUser(BaseModel):
    """User data returned from Hevy API login."""

    access_token: str
    user_id: str
    username: str | None = None
    email: str | None = None
    refresh_token: str | None = None
    expires_at: str | int | float | None = None
