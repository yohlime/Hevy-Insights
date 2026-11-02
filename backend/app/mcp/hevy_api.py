"""Thin client for Hevy's public (PRO) API, returning raw JSON.

The existing ``HevyAPIKeyClient`` normalizes workouts for the web frontend
(epoch timestamps, synthetic IDs). The MCP layer mirrors Hevy's own shapes,
so it uses this client instead.
"""

from __future__ import annotations

from typing import Any

import requests


JsonDict = dict[str, Any]
DEFAULT_BASE_URL = "https://api.hevyapp.com"


class HevyApiError(Exception):
    """Raised when Hevy's public API cannot satisfy a request."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class HevyApi:
    """Minimal Hevy public API client keyed by a Hevy PRO API key."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ):
        if not api_key:
            raise HevyApiError("A Hevy API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "api-key": api_key,
            }
        )

    # ------------------------------------------------------------------ HTTP

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        allow_404: bool = False,
        expect_json: bool = True,
    ) -> Any:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise HevyApiError(f"Request to Hevy failed: {exc}") from exc

        if response.status_code == 404 and allow_404:
            return None

        if response.status_code >= 400:
            detail = response.text.strip()[:300] or response.reason
            raise HevyApiError(
                f"Hevy API returned {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        if not expect_json or not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise HevyApiError("Hevy API returned invalid JSON") from exc

    # --------------------------------------------------------------- User

    def get_user_info(self) -> JsonDict | None:
        data = self._request("GET", "/v1/user/info", allow_404=True)
        if isinstance(data, dict):
            inner = data.get("data")
            return inner if isinstance(inner, dict) else data
        return None

    # ------------------------------------------------------------ Workouts

    def list_workouts(self, page: int = 1, page_size: int = 5) -> JsonDict:
        data = self._request(
            "GET",
            "/v1/workouts",
            params={"page": page, "pageSize": page_size},
        )
        return data if isinstance(data, dict) else {}

    def get_workout(self, workout_id: str) -> JsonDict | None:
        data = self._request("GET", f"/v1/workouts/{workout_id}", allow_404=True)
        return data if isinstance(data, dict) else None

    def create_workout(self, workout: JsonDict) -> JsonDict | None:
        data = self._request("POST", "/v1/workouts", json_body={"workout": workout})
        if not isinstance(data, dict):
            return None
        created = data.get("workout")
        if isinstance(created, list):
            return created[0] if created and isinstance(created[0], dict) else None
        return created if isinstance(created, dict) else None

    def update_workout(self, workout_id: str, workout: JsonDict) -> JsonDict | None:
        data = self._request(
            "PUT",
            f"/v1/workouts/{workout_id}",
            json_body={"workout": workout},
            allow_404=True,
        )
        return data if isinstance(data, dict) else None

    def list_workout_events(self, page: int = 1, page_size: int = 5, since: str = "1970-01-01T00:00:00Z") -> JsonDict:
        data = self._request(
            "GET",
            "/v1/workouts/events",
            params={"page": page, "pageSize": page_size, "since": since},
        )
        return data if isinstance(data, dict) else {}

    def get_workout_count(self) -> int:
        data = self._request("GET", "/v1/workouts/count")
        if isinstance(data, dict):
            count = data.get("workout_count")
            if isinstance(count, (int, float)):
                return int(count)
        return 0

    # ------------------------------------------------------------ Routines

    def list_routines(self, page: int = 1, page_size: int = 5) -> JsonDict:
        data = self._request(
            "GET",
            "/v1/routines",
            params={"page": page, "pageSize": page_size},
        )
        return data if isinstance(data, dict) else {}

    def get_routine(self, routine_id: str) -> JsonDict | None:
        data = self._request("GET", f"/v1/routines/{routine_id}", allow_404=True)
        if isinstance(data, dict):
            routine = data.get("routine")
            return routine if isinstance(routine, dict) else None
        return None

    def create_routine(self, routine: JsonDict) -> JsonDict | None:
        data = self._request("POST", "/v1/routines", json_body={"routine": routine})
        if isinstance(data, dict):
            created = data.get("routine")
            return created if isinstance(created, dict) else None
        return None

    def update_routine(self, routine_id: str, routine: JsonDict) -> JsonDict | None:
        data = self._request(
            "PUT",
            f"/v1/routines/{routine_id}",
            json_body={"routine": routine},
            allow_404=True,
        )
        if isinstance(data, dict):
            updated = data.get("routine")
            return updated if isinstance(updated, dict) else None
        return None

    # ------------------------------------------------------ Routine folders

    def list_routine_folders(self, page: int = 1, page_size: int = 10) -> JsonDict:
        data = self._request(
            "GET",
            "/v1/routine_folders",
            params={"page": page, "pageSize": page_size},
        )
        return data if isinstance(data, dict) else {}

    def get_routine_folder(self, folder_id: str) -> JsonDict | None:
        data = self._request("GET", f"/v1/routine_folders/{folder_id}", allow_404=True)
        return data if isinstance(data, dict) else None

    def create_routine_folder(self, title: str) -> JsonDict | None:
        data = self._request(
            "POST",
            "/v1/routine_folders",
            json_body={"folder": {"title": title}},
        )
        return data if isinstance(data, dict) else None

    # --------------------------------------------------- Exercise templates

    def list_exercise_templates(self, page: int = 1, page_size: int = 100) -> JsonDict:
        data = self._request(
            "GET",
            "/v1/exercise_templates",
            params={"page": page, "pageSize": page_size},
        )
        return data if isinstance(data, dict) else {}

    def get_exercise_template(self, exercise_template_id: str) -> JsonDict | None:
        data = self._request(
            "GET",
            f"/v1/exercise_templates/{exercise_template_id}",
            allow_404=True,
        )
        return data if isinstance(data, dict) else None

    def create_exercise_template(self, exercise: JsonDict) -> JsonDict | None:
        data = self._request(
            "POST",
            "/v1/exercise_templates",
            json_body={"exercise": exercise},
        )
        return data if isinstance(data, dict) else None

    def get_exercise_history(
        self,
        exercise_template_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[JsonDict]:
        params: dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        data = self._request(
            "GET",
            f"/v1/exercise_history/{exercise_template_id}",
            params=params or None,
            allow_404=True,
        )
        if isinstance(data, dict):
            history = data.get("exercise_history")
            if isinstance(history, list):
                return [item for item in history if isinstance(item, dict)]
        return []

    # --------------------------------------------------- Body measurements

    def list_body_measurements(self, page: int = 1, page_size: int = 10) -> JsonDict:
        data = self._request(
            "GET",
            "/v1/body_measurements",
            params={"page": page, "pageSize": page_size},
        )
        return data if isinstance(data, dict) else {}

    def get_body_measurement(self, date: str) -> JsonDict | None:
        data = self._request("GET", f"/v1/body_measurements/{date}", allow_404=True)
        return data if isinstance(data, dict) else None

    def create_body_measurement(self, measurement: JsonDict) -> None:
        self._request("POST", "/v1/body_measurements", json_body=measurement, expect_json=False)

    def update_body_measurement(self, date: str, measurement: JsonDict) -> None:
        self._request(
            "PUT",
            f"/v1/body_measurements/{date}",
            json_body=measurement,
            allow_404=True,
            expect_json=False,
        )
