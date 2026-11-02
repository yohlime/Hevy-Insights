import asyncio
import json
import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.clients.hevy import HevyOAuthClient
from app.mcp.auth import McpTrailingSlashMiddleware
from app.mcp.hevy_api import HevyApi
from app.mcp.server import create_mcp_app, server


os.environ.setdefault("X_API_KEY", "test")

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def make_app() -> FastAPI:
    mcp_app = create_mcp_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(McpTrailingSlashMiddleware)
    app.mount("/mcp", mcp_app)
    return app


def rpc(client: TestClient, method: str, params: dict | None = None, headers: dict | None = None) -> dict:
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    response = client.post("/mcp", json=body, headers={**MCP_HEADERS, **(headers or {})})
    assert response.status_code == 200, response.text
    return response.json()


def initialize(client: TestClient, headers: dict) -> None:
    rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
        headers,
    )


def call_tool(client: TestClient, name: str, arguments: dict, headers: dict) -> dict:
    initialize(client, headers)
    return rpc(client, "tools/call", {"name": name, "arguments": arguments}, headers)


class McpToolSurfaceTests(unittest.TestCase):
    def test_registers_the_hevy_mcp_tool_surface(self) -> None:
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(len(names), 23)
        self.assertIn("get-workouts", names)
        self.assertIn("create-workout", names)
        self.assertIn("update-routine", names)
        self.assertIn("get-training-summary", names)
        self.assertIn("feedback", names)
        self.assertNotIn("get-user-info", names)


class McpToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(make_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_missing_api_key_returns_tool_error(self) -> None:
        data = call_tool(self.client, "get-workouts", {"page": 1, "page_size": 5}, headers={})
        result = data["result"]
        self.assertTrue(result["isError"])
        self.assertIn("Missing Hevy credentials", result["content"][0]["text"])

    def test_get_workouts_uses_api_key_and_formats_summary(self) -> None:
        captured: dict = {}

        def fake_list_workouts(self, page=1, page_size=5):
            captured["api_key"] = self.api_key
            captured["page"] = page
            captured["page_size"] = page_size
            return {
                "workouts": [
                    {
                        "id": "w1",
                        "title": "Push",
                        "start_time": "2024-01-01T10:00:00Z",
                        "end_time": "2024-01-01T11:00:00Z",
                        "exercises": [{"exercise_template_id": "t1", "sets": [{"weight_kg": 100, "reps": 5}]}],
                    }
                ],
                "page": 1,
                "page_count": 2,
            }

        with patch.object(HevyApi, "list_workouts", fake_list_workouts):
            data = call_tool(
                self.client,
                "get-workouts",
                {"page": 1, "page_size": 5},
                {"api-key": "secret-key"},
            )

        self.assertEqual(captured["api_key"], "secret-key")
        structured = data["result"]["structuredContent"]
        self.assertEqual(structured["page"], 1)
        self.assertEqual(structured["page_count"], 2)
        self.assertTrue(structured["has_next_page"])
        self.assertEqual(structured["workouts"][0]["exercise_count"], 1)
        self.assertEqual(structured["workouts"][0]["set_count"], 1)
        self.assertEqual(structured["workouts"][0]["duration"], "1h 0m 0s")

    def test_create_routine_sends_snake_case_payload_and_rep_ranges(self) -> None:
        captured: dict = {}

        def fake_create_routine(self, routine):
            captured["routine"] = routine
            return {"id": "r1", "title": routine["title"], "exercises": routine["exercises"]}

        arguments = {
            "routine": {
                "title": "Push",
                "notes": "Controlled",
                "exercises": [
                    {
                        "exercise_template_id": "t1",
                        "rest_seconds": 60,
                        "sets": [{"type": "normal", "reps": 8, "rep_range": {"start": 6, "end": 10}}],
                    }
                ],
            }
        }

        with patch.object(HevyApi, "create_routine", fake_create_routine):
            data = call_tool(
                self.client,
                "create-routine",
                arguments,
                {"api-key": "secret-key"},
            )

        structured = data["result"]["structuredContent"]
        self.assertEqual(structured["routine_id"], "r1")
        self.assertTrue(structured["uses_rep_ranges"])
        self.assertEqual(captured["routine"]["exercises"][0]["sets"][0]["rep_range"], {"start": 6, "end": 10})

    def test_update_workout_preserves_existing_exercises(self) -> None:
        current = {
            "id": "w1",
            "title": "Old",
            "description": "Keep",
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T11:00:00Z",
            "is_private": False,
            "exercises": [
                {
                    "index": 0,
                    "title": "Bench",
                    "exercise_template_id": "t1",
                    "superset_id": None,
                    "notes": "note",
                    "sets": [{"index": 0, "type": "normal", "weight_kg": 100, "reps": 5}],
                }
            ],
        }
        captured: dict = {}

        def fake_get_workout(self, workout_id):
            return current

        def fake_update_workout(self, workout_id, workout):
            captured["workout_id"] = workout_id
            captured["workout"] = workout
            return {**current, **workout}

        with (
            patch.object(HevyApi, "get_workout", fake_get_workout),
            patch.object(HevyApi, "update_workout", fake_update_workout),
        ):
            data = call_tool(
                self.client,
                "update-workout",
                {"workout_id": "w1", "workout": {"title": "New", "is_private": True}},
                {"api-key": "secret-key"},
            )

        self.assertFalse(data["result"]["isError"])
        payload = captured["workout"]
        self.assertEqual(payload["title"], "New")
        self.assertTrue(payload["is_private"])
        self.assertEqual(payload["description"], "Keep")
        self.assertEqual(payload["exercises"][0]["exercise_template_id"], "t1")
        self.assertEqual(payload["exercises"][0]["sets"][0]["reps"], 5)

    def test_training_summary_computes_window_totals(self) -> None:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        early_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
        late_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        def fake_list_workouts(self, page=1, page_size=5):
            return {
                "workouts": [
                    {
                        "id": "w1",
                        "title": "Push",
                        "start_time": start,
                        "end_time": end,
                        "exercises": [
                            {
                                "exercise_template_id": "t1",
                                "sets": [{"weight_kg": 100, "reps": 5}, {"weight_kg": 90, "reps": 8}],
                            }
                        ],
                    }
                ],
                "page": 1,
                "page_count": 1,
            }

        def fake_list_body_measurements(self, page=1, page_size=10):
            return {
                "body_measurements": [
                    {"date": early_date, "weight_kg": 80},
                    {"date": late_date, "weight_kg": 79.5},
                ],
                "page": 1,
                "page_count": 1,
            }

        with (
            patch.object(HevyApi, "list_workouts", fake_list_workouts),
            patch.object(HevyApi, "list_body_measurements", fake_list_body_measurements),
        ):
            data = call_tool(
                self.client,
                "get-training-summary",
                {"weeks": 4},
                {"api-key": "secret-key"},
            )

        structured = data["result"]["structuredContent"]
        self.assertEqual(structured["workouts"]["count"], 1)
        self.assertEqual(structured["workouts"]["set_count"], 2)
        self.assertEqual(structured["workouts"]["total_volume_kg"], 1220.0)
        self.assertEqual(structured["workouts"]["unique_exercise_template_ids"], ["t1"])
        self.assertEqual(structured["body_measurements"]["count"], 2)
        self.assertAlmostEqual(structured["body_measurements"]["weight_change_kg"], -0.5)

    def test_user_resource_reads_with_request_api_key(self) -> None:
        def fake_get_user_info(self):
            return {"id": "u1", "username": "tester"}

        with patch.object(HevyApi, "get_user_info", fake_get_user_info):
            initialize(self.client, {"Authorization": "Bearer secret-key"})
            data = rpc(
                self.client,
                "resources/read",
                {"uri": "hevy://user"},
                {"api-key": "secret-key"},
            )

        contents = data["result"]["contents"]
        self.assertEqual(json.loads(contents[0]["text"]), {"id": "u1", "username": "tester"})

    def test_analyze_workout_progress_prompt_uses_weeks(self) -> None:
        initialize(self.client, {"Authorization": "Bearer secret-key"})
        data = rpc(
            self.client,
            "prompts/get",
            {"name": "analyze-workout-progress", "arguments": {"weeks": "6"}},
            {"Authorization": "Bearer secret-key"},
        )
        text = data["result"]["messages"][0]["content"]["text"]
        self.assertIn("last 6 weeks", text)
        self.assertIn("get-training-summary", text)


    def test_oauth_bearer_uses_web_api(self) -> None:
        def fake_get_user_account(self):
            return {"username": "tester", "id": "u1"}

        def fake_get_workouts(self, username, offset=0):
            return {
                "workouts": [
                    {
                        "id": "w1",
                        "title": "Push",
                        "start_time": 1700000000,
                        "end_time": 1700003600,
                        "exercises": [{"exercise_template_id": "t1", "sets": [{"weight_kg": 100, "reps": 5}]}],
                    }
                ]
            }

        def fake_get_workout_count(self, username):
            return 1

        with (
            patch("app.mcp.backend.get_auth_session", return_value=None),
            patch.object(HevyOAuthClient, "get_user_account", fake_get_user_account),
            patch.object(HevyOAuthClient, "get_workouts", fake_get_workouts),
            patch.object(HevyOAuthClient, "get_workout_count", fake_get_workout_count),
        ):
            data = call_tool(
                self.client,
                "get-workouts",
                {"page": 1, "page_size": 5},
                {"Authorization": "Bearer oauth-token"},
            )

        self.assertFalse(data["result"]["isError"])
        structured = data["result"]["structuredContent"]
        self.assertEqual(structured["workouts"][0]["id"], "w1")
        self.assertEqual(structured["workouts"][0]["duration"], "1h 0m 0s")
        self.assertEqual(structured["page_count"], 1)

    def test_oauth_session_id_resolves_auth_session(self) -> None:
        fake_session = SimpleNamespace(
            session_id="sid",
            user_id="u1",
            access_token="token",
            refresh_token=None,
            expires_at=None,
            saved_account_secret="secret",
        )
        fake_client = HevyOAuthClient(access_token="token")

        with (
            patch("app.mcp.backend.get_auth_session", return_value=fake_session),
            patch("app.mcp.backend.get_hevy_client", return_value=fake_client),
            patch.object(HevyOAuthClient, "get_user_account", lambda self: {"username": "tester"}),
            patch.object(HevyOAuthClient, "get_workouts", lambda self, username, offset=0: {"workouts": []}),
            patch.object(HevyOAuthClient, "get_workout_count", lambda self, username: 0),
        ):
            data = call_tool(
                self.client,
                "get-workouts",
                {"page": 1, "page_size": 5},
                {"Authorization": "Bearer sid"},
            )

        self.assertFalse(data["result"]["isError"])
        self.assertEqual(data["result"]["structuredContent"]["workouts"], [])

    def test_oauth_get_workout_scans_web_api(self) -> None:
        def fake_get_user_account(self):
            return {"username": "tester"}

        def fake_get_workouts(self, username, offset=0):
            return {
                "workouts": [
                    {
                        "id": "w1",
                        "title": "Push",
                        "start_time": 1700000000,
                        "end_time": 1700003600,
                        "exercises": [],
                    }
                ]
            }

        with (
            patch("app.mcp.backend.get_auth_session", return_value=None),
            patch("app.mcp.backend.get_cached_workout", return_value=None),
            patch.object(HevyOAuthClient, "get_user_account", fake_get_user_account),
            patch.object(HevyOAuthClient, "get_workouts", fake_get_workouts),
        ):
            data = call_tool(
                self.client,
                "get-workout",
                {"workout_id": "w1"},
                {"Authorization": "Bearer oauth-token"},
            )

        self.assertFalse(data["result"]["isError"])
        self.assertEqual(data["result"]["structuredContent"]["workout"]["id"], "w1")

    def test_oauth_create_routine_translates_to_web_shape(self) -> None:
        captured: dict = {}

        def fake_create_routine(self, routine):
            captured["routine"] = routine
            return {"routineId": "r1"}

        with (
            patch("app.mcp.backend.get_auth_session", return_value=None),
            patch.object(HevyOAuthClient, "create_routine", fake_create_routine),
        ):
            data = call_tool(
                self.client,
                "create-routine",
                {
                    "routine": {
                        "title": "Push",
                        "exercises": [
                            {
                                "exercise_template_id": "t1",
                                "sets": [
                                    {
                                        "type": "normal",
                                        "reps": 8,
                                        "rep_range": {"start": 6, "end": 10},
                                    }
                                ],
                            }
                        ],
                    }
                },
                {"Authorization": "Bearer oauth-token"},
            )

        self.assertFalse(data["result"]["isError"])
        self.assertEqual(data["result"]["structuredContent"]["routine_id"], "r1")
        internal_set = captured["routine"]["exercises"][0]["sets"][0]
        self.assertEqual(internal_set["indicator"], "normal")
        self.assertEqual(internal_set["index"], 0)
        self.assertEqual(internal_set["rep_range"], {"start": 6, "end": 10})

    def test_oauth_rejects_pro_only_mutation(self) -> None:
        with patch("app.mcp.backend.get_auth_session", return_value=None):
            data = call_tool(
                self.client,
                "create-workout",
                {
                    "workout": {
                        "title": "Push",
                        "start_time": "2024-01-01T10:00:00Z",
                        "end_time": "2024-01-01T11:00:00Z",
                        "exercises": [{"exercise_template_id": "t1", "sets": [{"type": "normal", "reps": 5}]}],
                    }
                },
                {"Authorization": "Bearer oauth-token"},
            )

        self.assertTrue(data["result"]["isError"])
        self.assertIn("requires a Hevy PRO API key", data["result"]["content"][0]["text"])

    def test_oauth_user_resource(self) -> None:
        with (
            patch("app.mcp.backend.get_auth_session", return_value=None),
            patch.object(HevyOAuthClient, "get_user_account", lambda self: {"username": "tester", "id": "u1"}),
        ):
            initialize(self.client, {"Authorization": "Bearer oauth-token"})
            data = rpc(
                self.client,
                "resources/read",
                {"uri": "hevy://user"},
                {"Authorization": "Bearer oauth-token"},
            )

        self.assertEqual(json.loads(data["result"]["contents"][0]["text"]), {"username": "tester", "id": "u1"})


class McpTokenEndpointTests(unittest.TestCase):
    def test_returns_oauth_session_id(self) -> None:
        from app.api.router import api_router

        app = FastAPI()
        app.include_router(api_router)
        client = TestClient(app)
        client.cookies.set("hevy_session_id", "sid")

        response = client.get("/api/mcp/token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "oauth")
        self.assertEqual(response.json()["value"], "Bearer sid")

    def test_returns_api_key_for_pro_sessions(self) -> None:
        from app.api.router import api_router

        app = FastAPI()
        app.include_router(api_router)
        client = TestClient(app)
        client.cookies.set("hevy_api_key", "pro-key")

        response = client.get("/api/mcp/token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "api_key")
        self.assertEqual(response.json()["value"], "pro-key")

    def test_requires_authentication(self) -> None:
        from app.api.router import api_router

        app = FastAPI()
        app.include_router(api_router)
        client = TestClient(app)

        response = client.get("/api/mcp/token")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
