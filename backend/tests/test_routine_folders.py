from unittest import TestCase
from unittest.mock import patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.routes import routines as routine_routes
from app.clients.hevy import HevyOAuthClient


def _create_client() -> TestClient:
    app = FastAPI()
    router = APIRouter(prefix="/api")
    router.include_router(routine_routes.router)
    app.include_router(router)
    return TestClient(app)


class _FakeRouteHevyOAuthClient(HevyOAuthClient):
    def __init__(self):
        pass

    def create_routine_folder(self, title: str) -> dict[str, object]:
        return {
            "id": 3488643,
            "index": 0,
            "title": title,
            "updated_at": "2026-08-23T12:56:11.414Z",
            "created_at": "2026-08-23T12:56:11.414Z",
        }

    def get_routine_folders(self) -> dict[str, object]:
        return {"routine_folders": [{"id": 3488643, "title": "test"}]}

    def update_routine_folder(self, folder_id: str, title: str) -> dict[str, object]:
        return {"folderId": folder_id, "title": title}

    def delete_routine_folder(self, folder_id: str) -> dict[str, object]:
        return {"folderId": folder_id}

    def create_routine(self, routine: dict[str, object]) -> dict[str, object]:
        return {"routineId": "29298b06-5265-4887-9889-3b88f001529d"}

    def get_routine(self, routine_id: str) -> dict[str, object]:
        return {"routine": {"id": routine_id, "title": "test routine"}}

    def update_routine(self, routine_id: str, routine: dict[str, object]) -> dict[str, object]:
        return {"routineId": routine_id}

    def delete_routine(self, routine_id: str) -> dict[str, object]:
        return {"routineId": routine_id}


class _FakeConfig:
    x_api_key = "static-api-key"
    routine_folder_url = "https://api.hevyapp.com/routine_folder"
    routine_folders_url = "https://api.hevyapp.com/routine_folders"
    routine_url = "https://api.hevyapp.com/routine"


class _FakeResponse:
    def __init__(self, data: dict[str, object] | None = None, text: str | None = None) -> None:
        self.data = data or {
            "id": 3488643,
            "index": 0,
            "title": "test",
            "updated_at": "2026-08-23T12:56:11.414Z",
            "created_at": "2026-08-23T12:56:11.414Z",
        }
        self.text = text if text is not None else "{}"

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, object]:
        return self.data


class _FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.delete_kwargs: dict[str, object] | None = None
        self.get_kwargs: dict[str, object] | None = None
        self.post_kwargs: dict[str, object] | None = None
        self.put_kwargs: dict[str, object] | None = None

    def delete(self, url: str, **kwargs: object) -> _FakeResponse:
        self.delete_kwargs = {"url": url, **kwargs}
        if "/routine_folder/" in url:
            return _FakeResponse({"folderId": "3488643"}, text="")
        return _FakeResponse({"routineId": "29298b06-5265-4887-9889-3b88f001529d"}, text="")

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        self.get_kwargs = {"url": url, **kwargs}
        if url.endswith("/routine_folders"):
            return _FakeResponse({"routine_folders": [{"id": 3488643, "title": "test"}]})
        return _FakeResponse({"routine": {"id": "29298b06-5265-4887-9889-3b88f001529d", "title": "test routine"}})

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.post_kwargs = {"url": url, **kwargs}
        if url.endswith("/routine"):
            return _FakeResponse({"routineId": "29298b06-5265-4887-9889-3b88f001529d"})
        return _FakeResponse()

    def put(self, url: str, **kwargs: object) -> _FakeResponse:
        self.put_kwargs = {"url": url, **kwargs}
        if url.endswith("/routine_folder"):
            return _FakeResponse({"folderId": "3488643", "title": "editfoldername"}, text="")
        return _FakeResponse({"routineId": "29298b06-5265-4887-9889-3b88f001529d"})


class RoutineFolderTests(TestCase):
    routine_payload = {
        "routine": {
            "title": "test routine",
            "exercises": [
                {
                    "exercise_template_id": "3BC06AD3",
                    "rest_seconds": 120,
                    "sets": [
                        {"index": 0, "indicator": "normal"},
                        {"index": 1, "indicator": "normal"},
                        {"index": 2, "indicator": "normal"},
                    ],
                    "notes": "",
                },
                {
                    "exercise_template_id": "A69FF221",
                    "rest_seconds": 120,
                    "sets": [
                        {"index": 0, "indicator": "normal"},
                        {"index": 1, "indicator": "normal"},
                        {"index": 2, "indicator": "normal"},
                    ],
                    "notes": "",
                },
            ],
            "folder_id": None,
            "index": 0,
            "program_id": None,
            "notes": None,
            "coach_force_rpe_enabled": False,
        }
    }

    def test_create_routine_folder_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.post("/api/routine_folders", json={"folder": {"title": "test"}})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": 3488643,
                "index": 0,
                "title": "test",
                "updated_at": "2026-08-23T12:56:11.414Z",
                "created_at": "2026-08-23T12:56:11.414Z",
            },
        )

    def test_oauth_client_posts_expected_routine_folder_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.create_routine_folder("test")

        self.assertEqual(result["title"], "test")
        self.assertEqual(session.post_kwargs["url"], "https://api.hevyapp.com/routine_folder")
        self.assertEqual(session.post_kwargs["params"], {"sendSyncEventToMobileApp": "true"})
        self.assertEqual(session.post_kwargs["json"], {"folder": {"title": "test"}})
        self.assertEqual(
            session.post_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_get_routine_folders_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.get("/api/routine_folders")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"routine_folders": [{"id": 3488643, "title": "test"}]})

    def test_oauth_client_gets_expected_routine_folders_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.get_routine_folders()

        self.assertEqual(result, {"routine_folders": [{"id": 3488643, "title": "test"}]})
        self.assertEqual(session.get_kwargs["url"], "https://api.hevyapp.com/routine_folders")
        self.assertEqual(
            session.get_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_update_routine_folder_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.put("/api/routine_folders/3488643", json={"title": "editfoldername"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"folderId": "3488643", "title": "editfoldername"})

    def test_oauth_client_puts_expected_routine_folder_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.update_routine_folder("3488643", "editfoldername")

        self.assertEqual(result, {"folderId": "3488643", "title": "editfoldername"})
        self.assertEqual(session.put_kwargs["url"], "https://api.hevyapp.com/routine_folder")
        self.assertEqual(session.put_kwargs["params"], {"sendSyncEventToMobileApp": "true"})
        self.assertEqual(session.put_kwargs["json"], {"folderId": "3488643", "title": "editfoldername"})
        self.assertEqual(
            session.put_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_delete_routine_folder_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.delete("/api/routine_folders/3488643")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"folderId": "3488643", "title": None})

    def test_oauth_client_deletes_expected_routine_folder_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.delete_routine_folder("3488643")

        self.assertEqual(result, {"folderId": "3488643"})
        self.assertEqual(session.delete_kwargs["url"], "https://api.hevyapp.com/routine_folder/3488643")
        self.assertEqual(session.delete_kwargs["params"], {"sendSyncEventToMobileApp": "true"})
        self.assertEqual(
            session.delete_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_create_routine_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.post("/api/routines", json=self.routine_payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"routineId": "29298b06-5265-4887-9889-3b88f001529d"})

    def test_oauth_client_posts_expected_routine_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.create_routine(self.routine_payload["routine"])

        self.assertEqual(result["routineId"], "29298b06-5265-4887-9889-3b88f001529d")
        self.assertEqual(session.post_kwargs["url"], "https://api.hevyapp.com/routine")
        self.assertEqual(session.post_kwargs["params"], {"sendSyncEventToMobileApp": "true"})
        self.assertEqual(session.post_kwargs["json"], self.routine_payload)
        self.assertEqual(
            session.post_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_get_routine_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.get("/api/routines/29298b06-5265-4887-9889-3b88f001529d")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"routine": {"id": "29298b06-5265-4887-9889-3b88f001529d", "title": "test routine"}},
        )

    def test_oauth_client_gets_expected_routine_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.get_routine("29298b06-5265-4887-9889-3b88f001529d")

        self.assertEqual(result["routine"], {"id": "29298b06-5265-4887-9889-3b88f001529d", "title": "test routine"})
        self.assertEqual(session.get_kwargs["url"], "https://api.hevyapp.com/routine/29298b06-5265-4887-9889-3b88f001529d")
        self.assertEqual(
            session.get_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_update_routine_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.put("/api/routines/29298b06-5265-4887-9889-3b88f001529d", json=self.routine_payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"routineId": "29298b06-5265-4887-9889-3b88f001529d"})

    def test_oauth_client_puts_expected_routine_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.update_routine("29298b06-5265-4887-9889-3b88f001529d", self.routine_payload["routine"])

        self.assertEqual(result["routineId"], "29298b06-5265-4887-9889-3b88f001529d")
        self.assertEqual(session.put_kwargs["url"], "https://api.hevyapp.com/routine/29298b06-5265-4887-9889-3b88f001529d")
        self.assertEqual(session.put_kwargs["params"], {"sendSyncEventToMobileApp": "true"})
        self.assertEqual(session.put_kwargs["json"], self.routine_payload)
        self.assertEqual(
            session.put_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )

    def test_oauth_client_returns_routine_id_for_blank_update_response(self) -> None:
        class BlankUpdateSession(_FakeSession):
            def put(self, url: str, **kwargs: object) -> _FakeResponse:
                self.put_kwargs = {"url": url, **kwargs}
                return _FakeResponse(text="")

        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = BlankUpdateSession()

        result = client.update_routine("29298b06-5265-4887-9889-3b88f001529d", self.routine_payload["routine"])

        self.assertEqual(result, {"routineId": "29298b06-5265-4887-9889-3b88f001529d"})

    def test_delete_routine_route_returns_hevy_response(self) -> None:
        with patch.object(routine_routes, "get_hevy_client", return_value=_FakeRouteHevyOAuthClient()):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.delete("/api/routines/29298b06-5265-4887-9889-3b88f001529d")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"routineId": "29298b06-5265-4887-9889-3b88f001529d"})

    def test_oauth_client_deletes_expected_routine_request(self) -> None:
        session = _FakeSession()
        client = HevyOAuthClient(access_token="access-token", config=_FakeConfig())
        client.session = session

        result = client.delete_routine("29298b06-5265-4887-9889-3b88f001529d")

        self.assertEqual(result, {"routineId": "29298b06-5265-4887-9889-3b88f001529d"})
        self.assertEqual(session.delete_kwargs["url"], "https://api.hevyapp.com/routine/29298b06-5265-4887-9889-3b88f001529d")
        self.assertEqual(session.delete_kwargs["params"], {"sendSyncEventToMobileApp": "true"})
        self.assertEqual(
            session.delete_kwargs["headers"],
            {
                "x-api-key": "static-api-key",
                "Content-Type": "application/json",
                "Hevy-Platform": "web",
                "auth-token": "access-token",
                "Authorization": "Bearer access-token",
            },
        )
