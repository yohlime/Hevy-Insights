from typing import overload

from fastapi import HTTPException, Response

from app.clients.hevy import HevyAPIKeyClient, HevyError, HevyOAuthClient
from app.core.config import settings
from app.services.auth_sessions import delete_auth_session, get_auth_session, is_access_token_expired, update_auth_session_tokens


def set_auth_cookies(
    response: Response,
    access_token: str | None = None,
    refresh_token: str | None = None,
    api_key: str | None = None,
    expires_at: str | int | None = None,
    session_id: str | None = None,
) -> None:
    if access_token:
        response.set_cookie(
            key="hevy_access_token",
            value=access_token,
            max_age=settings.cookie_max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
        )

    if refresh_token:
        response.set_cookie(
            key="hevy_refresh_token",
            value=refresh_token,
            max_age=settings.cookie_max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
        )

    if expires_at:
        response.set_cookie(
            key="hevy_token_expires_at",
            value=str(expires_at),
            max_age=settings.cookie_max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
        )

    if api_key:
        response.set_cookie(
            key="hevy_api_key",
            value=api_key,
            max_age=settings.cookie_max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
        )

    if session_id:
        response.set_cookie(
            key="hevy_session_id",
            value=session_id,
            max_age=settings.auth_session_max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
        )


def clear_auth_cookies(response: Response) -> None:
    cookie_names = [
        "hevy_access_token",
        "hevy_refresh_token",
        "hevy_api_key",
        "hevy_token_expires_at",
        "hevy_session_id",
    ]
    for cookie_name in cookie_names:
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
        )

@overload
def get_hevy_client(
    access_token_cookie: str | None = None,
    *,
    api_key_cookie: str,
    session_id_cookie: str | None = None,
) -> HevyAPIKeyClient: ...


@overload
def get_hevy_client(
    access_token_cookie: str | None = None,
    api_key_cookie: None = None,
    session_id_cookie: str | None = None,
) -> HevyOAuthClient: ...


def get_hevy_client(
    access_token_cookie: str | None = None,
    api_key_cookie: str | None = None,
    session_id_cookie: str | None = None,
) -> HevyOAuthClient | HevyAPIKeyClient:
    if access_token_cookie == "csv_mode":
        raise HTTPException(
            status_code=400,
            detail="CSV mode does not support backend API calls. Data is stored client-side only.",
        )

    if api_key_cookie:
        return HevyAPIKeyClient(api_key=api_key_cookie)

    if session_id_cookie:
        auth_session = get_auth_session(session_id_cookie)
        if auth_session:
            if is_access_token_expired(auth_session.expires_at):
                if not auth_session.saved_account_secret:
                    raise HTTPException(status_code=401, detail="Session expired. Please login again.")

                client = HevyOAuthClient()
                try:
                    user = client.login_with_saved_account(
                        user_id=auth_session.user_id,
                        secret=auth_session.saved_account_secret,
                    )
                except HevyError as e:
                    delete_auth_session(session_id_cookie)
                    raise HTTPException(status_code=401, detail=str(e))
                update_auth_session_tokens(session_id_cookie, user)
                return client

            return HevyOAuthClient(access_token=auth_session.access_token)

    if access_token_cookie and access_token_cookie != "api_key_mode":
        return HevyOAuthClient(access_token=access_token_cookie)

    raise HTTPException(
        status_code=401,
        detail="Missing authentication: please login again",
    )
