"""Backends for the MCP tools: Hevy PRO public API or free OAuth web API."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from math import ceil
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.clients.hevy import HevyAPIKeyClient, HevyError, HevyOAuthClient
from app.core.security import get_hevy_client
from app.mcp.auth import current_credentials
from app.mcp.hevy_api import HevyApi
from app.services.auth_sessions import get_auth_session
from app.services.workout_cache import get_cached_workout, oauth_account_key


JsonDict = dict[str, Any]


class McpAuthError(Exception):
    """Raised when an MCP request has no usable Hevy credentials."""


class UnsupportedOperation(Exception):
    """Raised when the OAuth web API cannot provide a PRO-only operation."""


def _looks_like_api_key(token: str) -> bool:
    """Hevy API keys are UUIDs; OAuth session ids are not."""
    try:
        UUID(token)
    except (ValueError, AttributeError):
        return False
    return True


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


class PublicApiBackend:
    """Hevy PRO public API (``/v1/*``)."""

    mode = "api_key"

    def __init__(self, api: HevyApi):
        self.api = api
        self.cache_key = hashlib.sha256(api.api_key.encode("utf-8")).hexdigest()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.api, name)


class OAuthBackend:
    """Hevy's internal web API, used by free OAuth accounts.

    The web API exposes workouts, routines, routine folders, and body
    measurements, but not the PRO-only workout mutations, workout events,
    exercise-template writes, or measurement updates.
    """

    mode = "oauth"

    def __init__(self, client: HevyOAuthClient):
        self.client = client
        token = client.access_token or ""
        self.cache_key = hashlib.sha256(f"oauth:{token}".encode("utf-8")).hexdigest()
        self._account: JsonDict | None = None
        self._username: str | None = None
        self._workout_scan: list[JsonDict] | None = None
        self._routines_cache: list[JsonDict] | None = None
        self._folders_cache: list[JsonDict] | None = None
        self._measurements_cache: list[JsonDict] | None = None
        self._count_cache: int | None = None

    # -------------------------------------------------------------- account

    def get_user_info(self) -> JsonDict | None:
        return self._get_account()

    def _get_account(self) -> JsonDict:
        if self._account is None:
            self._account = self.client.get_user_account() or {}
        return self._account

    def _get_username(self) -> str:
        if self._username is None:
            account = self._get_account()
            self._username = str(account.get("username") or account.get("name") or "")
        if not self._username:
            raise UnsupportedOperation("Hevy account did not return a username")
        return self._username

    def _scan_workouts(self, limit: int = 500) -> list[JsonDict]:
        """Fetch up to ``limit`` workouts once per request for derived data."""
        if self._workout_scan is not None:
            return self._workout_scan

        workouts: list[JsonDict] = []
        offset = 0
        while len(workouts) < limit:
            data = self.client.get_workouts(self._get_username(), offset)
            batch = [item for item in data.get("workouts") or [] if isinstance(item, dict)]
            if not batch:
                break
            workouts.extend(batch)
            if len(batch) < 5:
                break
            offset += 5

        self._workout_scan = workouts[:limit]
        return self._workout_scan

    # -------------------------------------------------------------- workouts

    def get_workout_count(self) -> int:
        if self._count_cache is None:
            self._count_cache = self.client.get_workout_count(self._get_username())
        return self._count_cache

    def list_workouts(self, page: int = 1, page_size: int = 5) -> JsonDict:
        # The web API pages by offset in increments of five.
        start = (page - 1) * page_size
        upstream_start = (start // 5) * 5
        skip = start - upstream_start

        collected: list[JsonDict] = []
        offset = upstream_start
        while len(collected) < skip + page_size:
            data = self.client.get_workouts(self._get_username(), offset)
            batch = [item for item in data.get("workouts") or [] if isinstance(item, dict)]
            if not batch:
                break
            collected.extend(batch)
            if len(batch) < 5:
                break
            offset += 5

        try:
            total = self.get_workout_count()
        except HevyError:
            total = 0
        return {
            "workouts": collected[skip : skip + page_size],
            "page": page,
            "page_count": ceil(total / page_size) if total > 0 else 0,
        }

    def get_workout(self, workout_id: str) -> JsonDict | None:
        cached = get_cached_workout(
            source="oauth",
            account_key=oauth_account_key(self._get_username()),
            workout_id=workout_id,
        )
        if cached:
            return cached

        for workout in self._scan_workouts():
            if str(workout.get("id")) == workout_id:
                return workout
        return None

    def list_workout_events(self, page: int = 1, page_size: int = 5, since: str = "") -> JsonDict:
        raise UnsupportedOperation("Workout events require a Hevy PRO API key")

    def create_workout(self, workout: JsonDict) -> JsonDict | None:
        raise UnsupportedOperation("Creating workouts requires a Hevy PRO API key")

    def update_workout(self, workout_id: str, workout: JsonDict) -> JsonDict | None:
        raise UnsupportedOperation("Updating workouts requires a Hevy PRO API key")

    # -------------------------------------------------------------- routines

    def _routine_ids(self) -> list[str]:
        seen: set[str] = set()
        routine_ids: list[str] = []
        for workout in self._scan_workouts():
            routine_id = workout.get("routine_id")
            if isinstance(routine_id, str) and routine_id and routine_id not in seen:
                seen.add(routine_id)
                routine_ids.append(routine_id)
        return routine_ids

    def list_routines(self, page: int = 1, page_size: int = 5) -> JsonDict:
        if self._routines_cache is None:
            routines = []
            for routine_id in self._routine_ids():
                try:
                    routine = self.get_routine(routine_id)
                except HevyError:
                    routine = None
                if routine:
                    routines.append(routine)
            self._routines_cache = routines

        routines = self._routines_cache
        start = (page - 1) * page_size
        total = len(routines)
        return {
            "routines": routines[start : start + page_size],
            "page": page,
            "page_count": ceil(total / page_size) if total > 0 else 0,
        }

    def get_routine(self, routine_id: str) -> JsonDict | None:
        data = self.client.get_routine(routine_id)
        if isinstance(data, dict):
            routine = data.get("routine")
            return routine if isinstance(routine, dict) else None
        return None

    def _internal_routine(self, routine: JsonDict) -> JsonDict:
        """Translate the public routine shape into the web app's shape."""
        exercises = []
        for exercise in routine.get("exercises") or []:
            sets = []
            for index, set_data in enumerate(exercise.get("sets") or []):
                set_type = set_data.get("type") or "normal"
                payload = {
                    "index": index,
                    "indicator": set_type,
                    "type": set_type,
                    "weight_kg": set_data.get("weight_kg"),
                    "reps": set_data.get("reps"),
                    "distance_meters": set_data.get("distance_meters"),
                    "duration_seconds": set_data.get("duration_seconds"),
                    "rep_range": set_data.get("rep_range"),
                    "custom_metric": set_data.get("custom_metric"),
                }
                sets.append({key: value for key, value in payload.items() if value is not None})

            exercise_payload = {
                "exercise_template_id": exercise.get("exercise_template_id"),
                "superset_id": exercise.get("superset_id"),
                "rest_seconds": exercise.get("rest_seconds"),
                "notes": exercise.get("notes"),
                "sets": sets,
            }
            exercises.append({key: value for key, value in exercise_payload.items() if value is not None})

        payload = {
            "title": routine.get("title"),
            "folder_id": routine.get("folder_id"),
            "notes": routine.get("notes"),
            "exercises": exercises,
        }
        return {key: value for key, value in payload.items() if value is not None}

    def create_routine(self, routine: JsonDict) -> JsonDict | None:
        created = self.client.create_routine(self._internal_routine(routine))
        routine_id = created.get("routineId") if isinstance(created, dict) else None
        if not routine_id:
            return None
        return {
            "id": str(routine_id),
            "title": routine.get("title"),
            "folder_id": routine.get("folder_id"),
            "notes": routine.get("notes"),
            "exercises": routine.get("exercises"),
        }

    def update_routine(self, routine_id: str, routine: JsonDict) -> JsonDict | None:
        self.client.update_routine(routine_id, self._internal_routine(routine))
        return {
            "id": routine_id,
            "title": routine.get("title"),
            "notes": routine.get("notes"),
            "exercises": routine.get("exercises"),
        }

    # --------------------------------------------------------- routine folders

    def _all_routine_folders(self) -> list[JsonDict]:
        if self._folders_cache is None:
            data = self.client.get_routine_folders()
            folders = data.get("routine_folders") if isinstance(data, dict) else None
            self._folders_cache = [item for item in folders or [] if isinstance(item, dict)]
        return self._folders_cache

    def list_routine_folders(self, page: int = 1, page_size: int = 10) -> JsonDict:
        folders = self._all_routine_folders()
        start = (page - 1) * page_size
        total = len(folders)
        return {
            "routine_folders": folders[start : start + page_size],
            "page": page,
            "page_count": ceil(total / page_size) if total > 0 else 0,
        }

    def get_routine_folder(self, folder_id: str) -> JsonDict | None:
        for folder in self._all_routine_folders():
            if str(folder.get("id")) == folder_id:
                return folder
        return None

    def create_routine_folder(self, title: str) -> JsonDict | None:
        return self.client.create_routine_folder(title)

    # ----------------------------------------------------- exercise templates

    def _derived_templates(self) -> list[JsonDict]:
        templates: dict[str, JsonDict] = {}
        for workout in self._scan_workouts():
            for exercise in workout.get("exercises") or []:
                template_id = exercise.get("exercise_template_id")
                if not isinstance(template_id, str) or not template_id or template_id in templates:
                    continue
                templates[template_id] = {
                    "id": template_id,
                    "title": exercise.get("title"),
                }
        return list(templates.values())

    def list_exercise_templates(self, page: int = 1, page_size: int = 100) -> JsonDict:
        templates = self._derived_templates()
        start = (page - 1) * page_size
        total = len(templates)
        return {
            "exercise_templates": templates[start : start + page_size],
            "page": page,
            "page_count": ceil(total / page_size) if total > 0 else 0,
        }

    def get_exercise_template(self, exercise_template_id: str) -> JsonDict | None:
        for template in self._derived_templates():
            if template.get("id") == exercise_template_id:
                return template
        return None

    def create_exercise_template(self, exercise: JsonDict) -> JsonDict | None:
        raise UnsupportedOperation("Creating exercise templates requires a Hevy PRO API key")

    def get_exercise_history(
        self,
        exercise_template_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[JsonDict]:
        start = _parse_datetime(start_date)
        end = _parse_datetime(end_date)

        history: list[JsonDict] = []
        for workout in self._scan_workouts():
            workout_start = _parse_datetime(workout.get("start_time"))
            if start and workout_start and workout_start < start:
                continue
            if end and workout_start and workout_start > end:
                continue

            for exercise in workout.get("exercises") or []:
                if exercise.get("exercise_template_id") != exercise_template_id:
                    continue
                for set_data in exercise.get("sets") or []:
                    history.append(
                        {
                            "workout_id": workout.get("id"),
                            "workout_title": workout.get("title"),
                            "workout_start_time": workout.get("start_time"),
                            "workout_end_time": workout.get("end_time"),
                            "exercise_template_id": exercise_template_id,
                            "weight_kg": set_data.get("weight_kg"),
                            "reps": set_data.get("reps"),
                            "distance_meters": set_data.get("distance_meters"),
                            "duration_seconds": set_data.get("duration_seconds"),
                            "rpe": set_data.get("rpe"),
                            "custom_metric": set_data.get("custom_metric"),
                            "set_type": set_data.get("type"),
                        }
                    )
        return history

    # ------------------------------------------------------ body measurements

    def _all_body_measurements(self) -> list[JsonDict]:
        if self._measurements_cache is None:
            measurements = self.client.get_body_measurements()
            self._measurements_cache = [item for item in measurements or [] if isinstance(item, dict)]
        return self._measurements_cache

    def list_body_measurements(self, page: int = 1, page_size: int = 10) -> JsonDict:
        measurements = self._all_body_measurements()
        start = (page - 1) * page_size
        total = len(measurements)
        return {
            "body_measurements": measurements[start : start + page_size],
            "page": page,
            "page_count": ceil(total / page_size) if total > 0 else 0,
        }

    def get_body_measurement(self, date: str) -> JsonDict | None:
        for measurement in self._all_body_measurements():
            if measurement.get("date") == date:
                return measurement
        return None

    def create_body_measurement(self, measurement: JsonDict) -> None:
        self.client.post_body_measurement_batch(measurement)

    def update_body_measurement(self, date: str, measurement: JsonDict) -> None:
        raise UnsupportedOperation("Updating body measurements requires a Hevy PRO API key")


def build_backend() -> PublicApiBackend | OAuthBackend:
    """Resolve the request credentials into a backend.

    Priority:
    1. ``api-key`` / ``x-api-key`` header -> Hevy PRO public API.
    2. Bearer token matching an ``auth_sessions`` row -> free OAuth session
       (refreshes through the saved-account secret when needed).
    3. ``hevy_session_id`` cookie -> free OAuth session.
    4. Bearer token treated as a raw OAuth access token.
    """
    credentials = current_credentials()

    if credentials.api_key:
        return PublicApiBackend(HevyApi(credentials.api_key))

    # hevy-mcp clients commonly send the PRO key as a bearer token.
    if credentials.bearer and _looks_like_api_key(credentials.bearer):
        return PublicApiBackend(HevyApi(credentials.bearer))

    session_id = credentials.session_id
    if credentials.bearer and get_auth_session(credentials.bearer):
        session_id = credentials.bearer

    if session_id:
        try:
            client = get_hevy_client(session_id_cookie=session_id)
        except HTTPException as exc:
            raise McpAuthError(str(exc.detail)) from exc
        if isinstance(client, HevyOAuthClient):
            return OAuthBackend(client)
        if isinstance(client, HevyAPIKeyClient):
            return PublicApiBackend(HevyApi(client.api_key))

    if credentials.bearer:
        return OAuthBackend(HevyOAuthClient(access_token=credentials.bearer))

    raise McpAuthError(
        "Missing Hevy credentials. Use `Authorization: Bearer <hevy_session_id>` for a free OAuth "
        "account, or `api-key: <hevy_api_key>` for a Hevy PRO account."
    )
