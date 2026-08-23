from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.routes import auth as auth_routes
from app.clients.hevy import HevyError
from app.schemas.hevy import HevyUser


def _create_client() -> TestClient:
    app = FastAPI()
    router = APIRouter(prefix="/api")
    router.include_router(auth_routes.router)
    app.include_router(router)
    return TestClient(app)


class _FakeHevyOAuthClient:
    instances: list["_FakeHevyOAuthClient"] = []
    refresh_error: HevyError | None = None

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token
        self.refresh_calls: list[str] = []
        self.saved_account_calls: list[tuple[str, str]] = []
        _FakeHevyOAuthClient.instances.append(self)

    def refresh_access_token(self, refresh_token: str) -> HevyUser:
        self.refresh_calls.append(refresh_token)
        if self.refresh_error:
            raise self.refresh_error
        return HevyUser(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            user_id="refresh-user-id",
            expires_at=123456,
        )

    def login_with_saved_account(self, user_id: str, secret: str) -> HevyUser:
        self.saved_account_calls.append((user_id, secret))
        return HevyUser(
            access_token="saved-access-token",
            refresh_token="saved-refresh-token",
            user_id=user_id,
            expires_at=654321,
        )


class RefreshTokenRouteTests(TestCase):
    def setUp(self) -> None:
        _FakeHevyOAuthClient.instances = []
        _FakeHevyOAuthClient.refresh_error = None

    def test_refresh_token_is_used_before_saved_account_session(self) -> None:
        auth_session = SimpleNamespace(
            session_id="session-id",
            user_id="session-user-id",
            saved_account_secret="saved-secret",
        )

        with (
            patch.object(auth_routes, "HevyOAuthClient", _FakeHevyOAuthClient),
            patch.object(auth_routes, "get_auth_session", return_value=auth_session),
            patch.object(auth_routes, "update_auth_session_tokens") as update_auth_session_tokens,
        ):
            client = _create_client()
            client.cookies.set("hevy_access_token", "old-access-token")
            client.cookies.set("hevy_refresh_token", "old-refresh-token")
            client.cookies.set("hevy_session_id", "session-id")
            response = client.post("/api/refresh_token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "new-access-token")
        self.assertEqual(_FakeHevyOAuthClient.instances[0].access_token, "old-access-token")
        self.assertEqual(_FakeHevyOAuthClient.instances[0].refresh_calls, ["old-refresh-token"])
        self.assertEqual(_FakeHevyOAuthClient.instances[0].saved_account_calls, [])
        update_auth_session_tokens.assert_called_once()

    def test_saved_account_session_is_used_when_refresh_token_fails(self) -> None:
        auth_session = SimpleNamespace(
            session_id="session-id",
            user_id="session-user-id",
            saved_account_secret="saved-secret",
        )
        _FakeHevyOAuthClient.refresh_error = HevyError("Invalid or expired refresh token")

        with (
            patch.object(auth_routes, "HevyOAuthClient", _FakeHevyOAuthClient),
            patch.object(auth_routes, "get_auth_session", return_value=auth_session),
            patch.object(auth_routes, "update_auth_session_tokens") as update_auth_session_tokens,
        ):
            client = _create_client()
            client.cookies.set("hevy_access_token", "old-access-token")
            client.cookies.set("hevy_refresh_token", "old-refresh-token")
            client.cookies.set("hevy_session_id", "session-id")
            response = client.post("/api/refresh_token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "saved-access-token")
        self.assertEqual(_FakeHevyOAuthClient.instances[0].refresh_calls, ["old-refresh-token"])
        self.assertEqual(_FakeHevyOAuthClient.instances[1].saved_account_calls, [("session-user-id", "saved-secret")])
        update_auth_session_tokens.assert_called_once()
