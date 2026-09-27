from unittest import TestCase
from unittest.mock import patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import sqlite as sqlite_dialect

from app.api.routes import workouts as workout_routes
from app.db.workouts import workouts_table
from app.services import workout_cache


def _create_client() -> TestClient:
    app = FastAPI()
    router = APIRouter(prefix="/api")
    router.include_router(workout_routes.router)
    app.include_router(router)
    return TestClient(app)


class WorkoutPaginationTests(TestCase):
    def test_oauth_workouts_use_requested_cache_limit(self) -> None:
        cached_workouts = [{"id": str(index), "title": f"Workout {index}", "exercises": []} for index in range(50)]

        with (
            patch.object(workout_routes, "get_hevy_client", return_value=object()),
            patch.object(workout_routes, "oauth_account_key", return_value="user"),
            patch.object(workout_routes, "should_sync_workouts", return_value=False) as should_sync_workouts,
            patch.object(workout_routes, "get_cached_workout_count", return_value=50) as get_cached_workout_count,
            patch.object(workout_routes, "get_cached_workouts", return_value=cached_workouts) as get_cached_workouts,
        ):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.get("/api/workouts", params={"username": "user", "offset": 0, "limit": 50})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["workouts"]), 50)
        self.assertEqual(response.json()["total_count"], 50)
        should_sync_workouts.assert_called_once_with(source="oauth", account_key="user", requested_offset=0, requested_limit=50)
        get_cached_workout_count.assert_called_once_with(
            source="oauth", account_key="user", start_epoch=None, end_epoch=None, name=None
        )
        get_cached_workouts.assert_called_once_with(
            source="oauth", account_key="user", offset=0, limit=50, start_epoch=None, end_epoch=None, name=None
        )

    def test_api_key_workouts_sync_in_hevy_sized_pages_and_return_requested_page_size(self) -> None:
        cached_workouts = [{"id": str(index), "title": f"Workout {index}", "exercises": []} for index in range(50)]

        with (
            patch.object(workout_routes, "get_hevy_client", return_value=object()) as get_hevy_client,
            patch.object(workout_routes, "api_key_account_key", return_value="account-key"),
            patch.object(workout_routes, "should_sync_workouts", return_value=True),
            patch.object(workout_routes, "_sync_api_key_workouts") as sync_api_key_workouts,
            patch.object(workout_routes, "get_cached_workout_count", return_value=120),
            patch.object(workout_routes, "get_cached_workouts", return_value=cached_workouts) as get_cached_workouts,
        ):
            client = _create_client()
            client.cookies.set("hevy_api_key", "api-key")
            response = client.get("/api/workouts", params={"page": 2, "page_size": 50})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["workouts"]), 50)
        self.assertEqual(response.json()["total_count"], 120)
        get_hevy_client.assert_called_once_with(api_key_cookie="api-key")
        sync_api_key_workouts.assert_called_once_with(
            client=sync_api_key_workouts.call_args.kwargs["client"],
            account_key="account-key",
            requested_offset=50,
            required_count=100,
        )
        get_cached_workouts.assert_called_once_with(
            source="api_key", account_key="account-key", offset=50, limit=50, start_epoch=None, end_epoch=None, name=None
        )

    def test_filters_and_total_count_are_forwarded(self) -> None:
        with (
            patch.object(workout_routes, "get_hevy_client", return_value=object()),
            patch.object(workout_routes, "oauth_account_key", return_value="user"),
            patch.object(workout_routes, "should_sync_workouts", return_value=False),
            patch.object(workout_routes, "get_cached_workout_count", return_value=7) as get_cached_workout_count,
            patch.object(workout_routes, "get_cached_workouts", return_value=[]) as get_cached_workouts,
        ):
            client = _create_client()
            client.cookies.set("hevy_access_token", "access-token")
            response = client.get(
                "/api/workouts",
                params={"username": "user", "offset": 0, "limit": 9, "start_epoch": 1000, "end_epoch": 2000, "name": "push"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_count"], 7)
        get_cached_workout_count.assert_called_once_with(
            source="oauth", account_key="user", start_epoch=1000, end_epoch=2000, name="push"
        )
        get_cached_workouts.assert_called_once_with(
            source="oauth", account_key="user", offset=0, limit=9, start_epoch=1000, end_epoch=2000, name="push"
        )

    def test_api_key_sync_fetches_hevy_in_ten_workout_pages(self) -> None:
        class FakeAPIKeyClient:
            def __init__(self) -> None:
                self.workout_calls: list[tuple[int, int]] = []

            def get_workout_count(self) -> int:
                return 12

            def get_workouts(self, page: int, page_size: int) -> dict[str, object]:
                self.workout_calls.append((page, page_size))
                return {"workouts": [{"id": f"workout-{page}", "exercises": []}]}

        client = FakeAPIKeyClient()
        with (
            patch.object(workout_routes, "get_cached_workout_count", return_value=0),
            patch.object(workout_routes, "store_workouts", return_value=False),
            patch.object(workout_routes, "mark_workout_sync") as mark_workout_sync,
        ):
            workout_routes._sync_api_key_workouts(
                client=client, account_key="account-key", requested_offset=0, required_count=20
            )

        self.assertEqual(client.workout_calls, [(1, 10), (2, 10)])
        mark_workout_sync.assert_called_once_with(source="api_key", account_key="account-key", fully_synced=True)

    def test_api_key_sync_stops_once_requested_window_is_cached(self) -> None:
        class FakeAPIKeyClient:
            def __init__(self) -> None:
                self.workout_calls: list[tuple[int, int]] = []

            def get_workout_count(self) -> int:
                return 100

            def get_workouts(self, page: int, page_size: int) -> dict[str, object]:
                self.workout_calls.append((page, page_size))
                return {"workouts": [{"id": f"workout-{page}-{i}", "exercises": []} for i in range(page_size)]}

        client = FakeAPIKeyClient()
        with (
            patch.object(workout_routes, "get_cached_workout_count", return_value=0),
            patch.object(workout_routes, "store_workouts", return_value=False),
            patch.object(workout_routes, "mark_workout_sync") as mark_workout_sync,
        ):
            workout_routes._sync_api_key_workouts(
                client=client, account_key="account-key", requested_offset=0, required_count=20
            )

        # Full 10-workout pages: stops after the requested window is covered.
        self.assertEqual(client.workout_calls, [(1, 10), (2, 10)])
        mark_workout_sync.assert_called_once_with(source="api_key", account_key="account-key", fully_synced=False)

    def test_sync_start_index_resumes_from_cache(self) -> None:
        with patch.object(workout_routes, "get_cached_workout_count", return_value=50):
            self.assertEqual(
                workout_routes._sync_start_index(source="oauth", account_key="k", requested_offset=60, page_size=5), 9
            )
            self.assertEqual(
                workout_routes._sync_start_index(source="oauth", account_key="k", requested_offset=0, page_size=5), 0
            )

    def test_should_sync_only_when_window_not_cached(self) -> None:
        with patch.object(workout_cache, "get_cached_workout_count", return_value=20):
            # offset 0 always refreshes the newest page
            self.assertTrue(
                workout_cache.should_sync_workouts(source="oauth", account_key="k", requested_offset=0, requested_limit=9)
            )
            # window already cached
            self.assertFalse(
                workout_cache.should_sync_workouts(source="oauth", account_key="k", requested_offset=11, requested_limit=9)
            )
            # window beyond the cache
            self.assertTrue(
                workout_cache.should_sync_workouts(source="oauth", account_key="k", requested_offset=30, requested_limit=9)
            )


class WorkoutCacheFilterTests(TestCase):
    def test_name_filter_escapes_like_wildcards(self) -> None:
        statement = workout_cache._apply_workout_filters(
            select(workouts_table.c.title),
            start_epoch=None,
            end_epoch=None,
            name="50%_x\\y",
        )

        compiled = statement.compile(dialect=sqlite_dialect.dialect())

        self.assertIn("ESCAPE", str(compiled))
        self.assertIn("%50\\%\\_x\\\\y%", list(compiled.params.values()))

    def test_date_filters_are_applied(self) -> None:
        statement = workout_cache._apply_workout_filters(
            select(workouts_table.c.title),
            start_epoch=100,
            end_epoch=200,
            name=None,
        )

        compiled = str(statement.compile(dialect=sqlite_dialect.dialect()))

        self.assertIn("start_time_epoch", compiled)
        self.assertEqual(len(list(statement.compile(dialect=sqlite_dialect.dialect()).params)), 2)
