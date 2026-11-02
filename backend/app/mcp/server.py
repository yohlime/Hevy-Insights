"""MCP server exposing the hevy-mcp tool contract.

Clients authenticate with either a free Hevy OAuth session id:

    Authorization: Bearer <hevy_session_id>
    # or the web app's hevy_session_id cookie

or a Hevy PRO API key:

    api-key: <hevy-api-key>
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from app.clients.hevy import HevyError
from app.mcp import formatters
from app.mcp.auth import ApiKeyMiddleware, NormalizeEmptyPathMiddleware
from app.mcp.backend import McpAuthError, UnsupportedOperation, build_backend
from app.mcp.hevy_api import HevyApiError
from app.mcp.models import (
    CALENDAR_DATE_PATTERN,
    ExerciseTemplatePayload,
    ReplaceWorkoutExercisesPayload,
    RoutineFolderPayload,
    RoutinePayload,
    MuscleGroup,
    RoutineUpdatePayload,
    WorkoutMetadataPatch,
    WorkoutPayload,
)


logger = logging.getLogger(__name__)

_CATALOG_TTL_SECONDS = 300
_catalog_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
CREATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
UPDATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)

server = MCPServer(
    name="hevy-insights",
    title="Hevy Insights MCP",
    description="Read and manage Hevy workouts, routines, folders, exercise templates, and body measurements.",
    instructions=(
        "Authenticate with a free OAuth session id (`Authorization: Bearer <hevy_session_id>`) or a Hevy PRO "
        "API key (`api-key: <key>`). PRO-only operations return a clear error on OAuth accounts. Read tools are "
        "safe to explore; create/update tools write to Hevy and may create duplicates when retried."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------- helpers


def _backend():
    return build_backend()


def _call(operation):
    try:
        return operation(_backend())
    except (HevyApiError, HevyError, McpAuthError, UnsupportedOperation) as exc:
        raise ToolError(str(exc)) from exc


def _pagination(page: int, page_count: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"page": page}
    if isinstance(page_count, int):
        result["page_count"] = page_count
        result["has_next_page"] = page < page_count
    return result


def _measurement_payload(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}


def _uses_rep_ranges(routine: RoutinePayload | RoutineUpdatePayload) -> bool:
    return any(exercise_set.rep_range is not None for exercise in routine.exercises for exercise_set in exercise.sets)


def _clean_set(set_data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: set_data[key]
        for key in ("type", "weight_kg", "reps", "distance_meters", "duration_seconds", "rpe", "custom_metric")
        if set_data.get(key) is not None
    }


def _clean_exercise(exercise: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "exercise_template_id": exercise.get("exercise_template_id"),
        "sets": [_clean_set(item) for item in exercise.get("sets") or [] if isinstance(item, dict)],
    }
    for key in ("superset_id", "notes"):
        if exercise.get(key) is not None:
            payload[key] = exercise[key]
    return payload


def _build_workout_update(
    current: dict[str, Any],
    patch: WorkoutMetadataPatch,
    replacement_exercises: list[Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": patch.title or current.get("title"),
        "start_time": patch.start_time or current.get("start_time"),
        "end_time": patch.end_time or current.get("end_time"),
        "is_private": patch.is_private,
        "exercises": (
            [exercise.model_dump(exclude_none=True) for exercise in replacement_exercises]
            if replacement_exercises is not None
            else [_clean_exercise(item) for item in current.get("exercises") or [] if isinstance(item, dict)]
        ),
    }
    description = patch.description if patch.description is not None else current.get("description")
    if description is not None:
        payload["description"] = description
    return payload


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


def _exercise_catalog(api: Any, *, refresh: bool = False) -> list[dict[str, Any]]:
    cache_key = api.cache_key
    now = time.time()
    cached = _catalog_cache.get(cache_key)
    if cached and not refresh and now - cached[0] < _CATALOG_TTL_SECONDS:
        return cached[1]

    templates: list[dict[str, Any]] = []
    page = 1
    while True:
        data = api.list_exercise_templates(page=page, page_size=100)
        batch = data.get("exercise_templates") or []
        templates.extend(item for item in batch if isinstance(item, dict))
        page_count = data.get("page_count")
        if not isinstance(page_count, int) or page >= page_count or not batch:
            break
        page += 1

    _catalog_cache[cache_key] = (now, templates)
    return templates


# --------------------------------------------------------------- workouts


@server.tool(
    name="get-workouts",
    description=(
        "Read-only. Lists compact workout summaries in Hevy API pagination order, not sorted by workout "
        "start_time. Use get-workout for exercises and sets; results are paginated."
    ),
    annotations=READ_ONLY,
)
def get_workouts(
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=10)] = 5,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        data = api.list_workouts(page=page, page_size=page_size)
        workouts = [formatters.summarize_workout(item) for item in data.get("workouts") or [] if isinstance(item, dict)]
        return {"workouts": workouts, **_pagination(data.get("page") or page, data.get("page_count"))}

    return _call(run)


@server.tool(
    name="get-workout",
    description="Read-only. Gets one workout with exercises and sets by workout_id. Use get-workouts to discover IDs.",
    annotations=READ_ONLY,
)
def get_workout(workout_id: str) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        workout = api.get_workout(workout_id)
        return {"workout": formatters.project_workout(workout) if workout else None}

    return _call(run)


@server.tool(
    name="get-workout-events",
    description="Read-only. Lists workout update and deletion events since a timestamp for incremental sync; results are paginated.",
    annotations=READ_ONLY,
)
def get_workout_events(
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=10)] = 5,
    since: str = "1970-01-01T00:00:00Z",
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        data = api.list_workout_events(page=page, page_size=page_size, since=since)
        events = [formatters.project_workout_event(item) for item in data.get("events") or [] if isinstance(item, dict)]
        return {"events": events, **_pagination(data.get("page") or page, data.get("page_count"))}

    return _call(run)


@server.tool(
    name="create-workout",
    description="Writes a completed workout. Requires exercise-template IDs and UTC times. Retries can create duplicates.",
    annotations=CREATE,
)
def create_workout(workout: WorkoutPayload) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        created = api.create_workout(workout.model_dump(exclude_none=True, mode="json"))
        if not created:
            raise ToolError("Failed to create workout: Server returned no data")
        return formatters.project_workout(created)

    return _call(run)


@server.tool(
    name="update-workout",
    description=(
        "Mutates workout metadata by ID. `is_private` is required; omitted fields and all exercises otherwise "
        "remain unchanged."
    ),
    annotations=UPDATE,
)
def update_workout(workout_id: str, workout: WorkoutMetadataPatch) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        current = api.get_workout(workout_id)
        if not current:
            raise ToolError(f"Workout with ID {workout_id} not found")
        payload = _build_workout_update(current, workout)
        updated = api.update_workout(workout_id, payload)
        if not updated:
            raise ToolError(f"Failed to update workout {workout_id}")
        return formatters.project_workout(updated)

    return _call(run)


@server.tool(
    name="replace-workout-exercises",
    description=(
        "Mutates a workout by replacing all exercises and sets. `is_private` is required and updated; other "
        "workout metadata remains unchanged."
    ),
    annotations=UPDATE,
)
def replace_workout_exercises(
    workout_id: str,
    workout: ReplaceWorkoutExercisesPayload,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        current = api.get_workout(workout_id)
        if not current:
            raise ToolError(f"Workout with ID {workout_id} not found")
        patch = WorkoutMetadataPatch(is_private=workout.is_private)
        payload = _build_workout_update(current, patch, replacement_exercises=workout.exercises)
        updated = api.update_workout(workout_id, payload)
        if not updated:
            raise ToolError(f"Failed to update workout {workout_id}")
        return formatters.project_workout(updated)

    return _call(run)


# --------------------------------------------------------------- routines


@server.tool(
    name="search-routines",
    description="Read-only. Searches routine titles and returns compact IDs and counts. Use get-routine for full exercises and sets.",
    annotations=READ_ONLY,
)
def search_routines(
    query: str | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        matches: list[dict[str, Any]] = []
        page = 1
        pages = 0
        items_scanned = 0
        needle = (query or "").lower()
        while len(matches) < limit:
            data = api.list_routines(page=page, page_size=10)
            batch = [item for item in data.get("routines") or [] if isinstance(item, dict)]
            pages += 1
            items_scanned += len(batch)
            for routine in batch:
                if needle and needle not in str(routine.get("title") or "").lower():
                    continue
                matches.append(formatters.summarize_routine(routine))
                if len(matches) >= limit:
                    break
            page_count = data.get("page_count")
            if not isinstance(page_count, int) or page >= page_count or not batch:
                break
            page += 1
        return {"routines": matches, "scan": {"pages": pages, "items": items_scanned}}

    return _call(run)


@server.tool(
    name="get-routines",
    description="Read-only. Lists compact routine summaries. Use get-routine for exercises and sets; results are paginated.",
    annotations=READ_ONLY,
)
def get_routines(
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=10)] = 5,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        data = api.list_routines(page=page, page_size=page_size)
        routines = [formatters.summarize_routine(item) for item in data.get("routines") or [] if isinstance(item, dict)]
        return {"routines": routines, **_pagination(data.get("page") or page, data.get("page_count"))}

    return _call(run)


@server.tool(
    name="get-routine",
    description="Read-only. Gets one routine with exercises and sets by routine_id. Use search-routines to discover IDs.",
    annotations=READ_ONLY,
)
def get_routine(routine_id: str) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        routine = api.get_routine(routine_id)
        return {"routine": formatters.project_routine(routine) if routine else None}

    return _call(run)


@server.tool(
    name="create-routine",
    description="Writes a reusable routine; use create-workout for completed sessions. Retries can create duplicates.",
    annotations=CREATE,
)
def create_routine(routine: RoutinePayload) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        created = api.create_routine(routine.model_dump(exclude_none=True, mode="json"))
        routine_id = created.get("id") if isinstance(created, dict) else None
        return {
            "created": True,
            "commit_state": "confirmed",
            "routine": formatters.project_routine(created) if created else None,
            "routine_id": routine_id,
            "uses_rep_ranges": _uses_rep_ranges(routine),
        }

    return _call(run)


@server.tool(
    name="update-routine",
    description="Mutates a routine by replacing its title and exercises. Omitted exercises are removed.",
    annotations=UPDATE,
)
def update_routine(routine_id: str, routine: RoutineUpdatePayload) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        updated = api.update_routine(routine_id, routine.model_dump(exclude_none=True, mode="json"))
        return {
            "updated": True,
            "commit_state": "confirmed",
            "routine": formatters.project_routine(updated) if updated else None,
            "routine_id": routine_id,
            "uses_rep_ranges": _uses_rep_ranges(routine),
        }

    return _call(run)


# -------------------------------------------------------- routine folders


@server.tool(
    name="get-routine-folder",
    description="Read-only. Gets one routine folder by folder_id. Use the hevy://routine-folders resource to discover IDs.",
    annotations=READ_ONLY,
)
def get_routine_folder(folder_id: str) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        folder = api.get_routine_folder(folder_id)
        return {"routine_folder": formatters.project_routine_folder(folder) if folder else None}

    return _call(run)


@server.tool(
    name="create-routine-folder",
    description="Writes a routine folder. Retries or reused titles can create duplicates.",
    annotations=CREATE,
)
def create_routine_folder(routine_folder: RoutineFolderPayload) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        created = api.create_routine_folder(routine_folder.title)
        folder_id = created.get("id") if isinstance(created, dict) else None
        return {
            "created": True,
            "commit_state": "confirmed",
            "routine_folder": formatters.project_routine_folder(created) if created else None,
            "folder_id": folder_id,
        }

    return _call(run)


# ------------------------------------------------------ exercise templates


@server.tool(
    name="get-exercise-template",
    description="Read-only. Gets one exercise template by exercise_template_id. Use search-exercise-templates to discover IDs.",
    annotations=READ_ONLY,
)
def get_exercise_template(exercise_template_id: str) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        template = api.get_exercise_template(exercise_template_id)
        return {"exercise_template": formatters.project_exercise_template(template) if template else None}

    return _call(run)


@server.tool(
    name="get-exercise-history",
    description="Read-only. Returns performed sets for one exercise-template ID, optionally bounded by ISO 8601 timestamps.",
    annotations=READ_ONLY,
)
def get_exercise_history(
    exercise_template_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        history = api.get_exercise_history(exercise_template_id, start_date=start_date, end_date=end_date)
        return {"exercise_history": [formatters.normalize_exercise_history_entry(item) for item in history]}

    return _call(run)


@server.tool(
    name="create-exercise-template",
    description="Writes a custom exercise template. Search first; retries or reused titles can create duplicates.",
    annotations=CREATE,
)
def create_exercise_template(exercise: ExerciseTemplatePayload) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        created = api.create_exercise_template(exercise.model_dump(exclude_none=True, mode="json"))
        return created or {}

    return _call(run)


@server.tool(
    name="search-exercise-templates",
    description="Read-only. Searches template titles case-insensitively and returns IDs. refresh reloads the five-minute catalog cache.",
    annotations=READ_ONLY,
)
def search_exercise_templates(
    query: str,
    primary_muscle_group: MuscleGroup | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        needle = query.lower()
        results = []
        for template in _exercise_catalog(api, refresh=refresh):
            if needle not in str(template.get("title") or "").lower():
                continue
            if primary_muscle_group and template.get("primary_muscle_group") != primary_muscle_group:
                continue
            results.append(formatters.project_exercise_template(template))
        return {"exercise_templates": results}

    return _call(run)


# ----------------------------------------------------- body measurements


@server.tool(
    name="get-body-measurements",
    description="Read-only. Lists dated body measurements; results are paginated. Use get-body-measurement for one date.",
    annotations=READ_ONLY,
)
def get_body_measurements(
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=10)] = 10,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        data = api.list_body_measurements(page=page, page_size=page_size)
        measurements = [
            formatters.normalize_body_measurement(item)
            for item in data.get("body_measurements") or []
            if isinstance(item, dict)
        ]
        return {"body_measurements": measurements, **_pagination(data.get("page") or page, data.get("page_count"))}

    return _call(run)


@server.tool(
    name="get-body-measurement",
    description="Read-only. Gets the body measurement for one YYYY-MM-DD date. Use get-body-measurements to browse dates.",
    annotations=READ_ONLY,
)
def get_body_measurement(date: Annotated[str, Field(pattern=CALENDAR_DATE_PATTERN)]) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        measurement = api.get_body_measurement(date)
        return {"body_measurement": formatters.normalize_body_measurement(measurement) if measurement else None}

    return _call(run)


@server.tool(
    name="create-body-measurement",
    description="Writes a body measurement for a new YYYY-MM-DD date. Existing dates conflict; retries are not idempotent.",
    annotations=CREATE,
)
def create_body_measurement(
    date: Annotated[str, Field(pattern=CALENDAR_DATE_PATTERN)],
    weight_kg: float | None = None,
    lean_mass_kg: float | None = None,
    fat_percent: float | None = None,
    neck_cm: float | None = None,
    shoulder_cm: float | None = None,
    chest_cm: float | None = None,
    left_bicep_cm: float | None = None,
    right_bicep_cm: float | None = None,
    left_forearm_cm: float | None = None,
    right_forearm_cm: float | None = None,
    abdomen: float | None = None,
    waist: float | None = None,
    hips: float | None = None,
    left_thigh: float | None = None,
    right_thigh: float | None = None,
    left_calf: float | None = None,
    right_calf: float | None = None,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        payload = _measurement_payload(
            weight_kg=weight_kg,
            lean_mass_kg=lean_mass_kg,
            fat_percent=fat_percent,
            neck_cm=neck_cm,
            shoulder_cm=shoulder_cm,
            chest_cm=chest_cm,
            left_bicep_cm=left_bicep_cm,
            right_bicep_cm=right_bicep_cm,
            left_forearm_cm=left_forearm_cm,
            right_forearm_cm=right_forearm_cm,
            abdomen=abdomen,
            waist=waist,
            hips=hips,
            left_thigh=left_thigh,
            right_thigh=right_thigh,
            left_calf=left_calf,
            right_calf=right_calf,
        )
        api.create_body_measurement({"date": date, **payload})
        return {"date": date}

    return _call(run)


@server.tool(
    name="update-body-measurement",
    description="Mutates numeric fields on an existing YYYY-MM-DD measurement. Omitted fields remain unchanged; values cannot be cleared.",
    annotations=UPDATE,
)
def update_body_measurement(
    date: Annotated[str, Field(pattern=CALENDAR_DATE_PATTERN)],
    weight_kg: float | None = None,
    lean_mass_kg: float | None = None,
    fat_percent: float | None = None,
    neck_cm: float | None = None,
    shoulder_cm: float | None = None,
    chest_cm: float | None = None,
    left_bicep_cm: float | None = None,
    right_bicep_cm: float | None = None,
    left_forearm_cm: float | None = None,
    right_forearm_cm: float | None = None,
    abdomen: float | None = None,
    waist: float | None = None,
    hips: float | None = None,
    left_thigh: float | None = None,
    right_thigh: float | None = None,
    left_calf: float | None = None,
    right_calf: float | None = None,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        payload = _measurement_payload(
            weight_kg=weight_kg,
            lean_mass_kg=lean_mass_kg,
            fat_percent=fat_percent,
            neck_cm=neck_cm,
            shoulder_cm=shoulder_cm,
            chest_cm=chest_cm,
            left_bicep_cm=left_bicep_cm,
            right_bicep_cm=right_bicep_cm,
            left_forearm_cm=left_forearm_cm,
            right_forearm_cm=right_forearm_cm,
            abdomen=abdomen,
            waist=waist,
            hips=hips,
            left_thigh=left_thigh,
            right_thigh=right_thigh,
            left_calf=left_calf,
            right_calf=right_calf,
        )
        if not payload:
            raise ToolError(
                "No measurement fields provided. Include at least one numeric measurement field (e.g. weight_kg) to update."
            )
        api.update_body_measurement(date, payload)
        return {"date": date}

    return _call(run)


# --------------------------------------------------------------- workflows


@server.tool(
    name="get-training-summary",
    description="Read-only. Summarizes workouts and body-measurement trends for the last 1-12 weeks, including compact session and scan evidence.",
    annotations=READ_ONLY,
)
def get_training_summary(
    weeks: Annotated[int, Field(ge=1, le=12)] = 4,
) -> dict[str, Any]:
    def run(api) -> dict[str, Any]:
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=weeks * 7)
        end_exclusive = end + timedelta(days=1)

        workout_items, workout_pages, workout_scanned = _scan_window(
            lambda page: api.list_workouts(page=page, page_size=10),
            "workouts",
            start,
            end_exclusive,
            lambda item: item.get("start_time"),
        )
        measurement_items, measurement_pages, measurement_scanned = _scan_window(
            lambda page: api.list_body_measurements(page=page, page_size=10),
            "body_measurements",
            start,
            end_exclusive,
            lambda item: item.get("date"),
        )

        sessions: list[dict[str, Any]] = []
        unique_templates: set[str] = set()
        total_duration = 0
        total_exercises = 0
        total_sets = 0
        total_volume = 0.0

        for workout in workout_items:
            exercises = [item for item in workout.get("exercises") or [] if isinstance(item, dict)]
            start_dt = _parse_datetime(workout.get("start_time"))
            end_dt = _parse_datetime(workout.get("end_time"))
            duration = (
                int((end_dt - start_dt).total_seconds())
                if start_dt and end_dt and end_dt >= start_dt
                else None
            )
            session: dict[str, Any] = {
                "exercise_count": len(exercises),
                "set_count": sum(len(item.get("sets") or []) for item in exercises),
            }
            for key in ("id", "title", "start_time", "end_time"):
                if workout.get(key) is not None:
                    session[key] = workout[key]
            if duration is not None:
                session["duration_seconds"] = duration
            sessions.append(session)

            total_duration += duration or 0
            total_exercises += len(exercises)
            total_sets += session["set_count"]
            for exercise in exercises:
                template_id = exercise.get("exercise_template_id")
                if template_id:
                    unique_templates.add(str(template_id))
                for set_data in exercise.get("sets") or []:
                    if not isinstance(set_data, dict):
                        continue
                    weight = set_data.get("weight_kg")
                    reps = set_data.get("reps")
                    if isinstance(weight, (int, float)) and isinstance(reps, (int, float)):
                        total_volume += float(weight) * float(reps)

        measurements = sorted(measurement_items, key=lambda item: str(item.get("date") or ""))
        earliest = _compact_measurement(measurements[0]) if measurements else None
        latest = _compact_measurement(measurements[-1]) if measurements else None
        weight_change = (
            latest["weight_kg"] - earliest["weight_kg"]
            if latest and earliest and "weight_kg" in latest and "weight_kg" in earliest
            else None
        )

        body_measurements: dict[str, Any] = {"count": len(measurements)}
        if latest:
            body_measurements["latest"] = latest
        if earliest:
            body_measurements["earliest"] = earliest
        if weight_change is not None:
            body_measurements["weight_change_kg"] = weight_change

        return {
            "period": {
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "weeks": weeks,
            },
            "workouts": {
                "count": len(sessions),
                "total_duration_seconds": total_duration,
                "exercise_count": total_exercises,
                "set_count": total_sets,
                "total_volume_kg": total_volume,
                "unique_exercise_template_ids": sorted(unique_templates),
                "sessions": sessions,
            },
            "body_measurements": body_measurements,
            "scan": {
                "pages": {"workouts": workout_pages, "body_measurements": measurement_pages},
                "items": workout_scanned + measurement_scanned,
            },
        }

    return _call(run)


def _scan_window(loader, collection: str, start: datetime, end: datetime, get_date) -> tuple[list[dict[str, Any]], int, int]:
    items: list[dict[str, Any]] = []
    pages = 0
    scanned = 0
    page = 1
    while True:
        try:
            data = loader(page)
        except HevyApiError as exc:
            if exc.status_code == 404:
                break
            raise
        batch = [item for item in data.get(collection) or [] if isinstance(item, dict)]
        pages += 1
        scanned += len(batch)
        for item in batch:
            timestamp = _parse_datetime(get_date(item))
            if timestamp is not None and start <= timestamp < end:
                items.append(item)
        page_count = data.get("page_count")
        if not isinstance(page_count, int) or page >= page_count or not batch:
            break
        page += 1
    return items, pages, scanned


def _compact_measurement(measurement: dict[str, Any]) -> dict[str, Any]:
    compact = {"date": measurement.get("date")}
    for key in ("weight_kg", "lean_mass_kg", "fat_percent"):
        if measurement.get(key) is not None:
            compact[key] = measurement[key]
    return compact


# ------------------------------------------------------------- diagnostics


@server.tool(
    name="feedback",
    description="Report a concise, privacy-safe description of an issue or unexpected behavior.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
def feedback(message: str) -> dict[str, Any]:
    cleaned = " ".join(message.split())[:2000]
    if not cleaned:
        return {"accepted": False, "reason": "rejected"}
    logger.debug("MCP feedback: %s", cleaned)
    return {"accepted": True}


# --------------------------------------------------------------- resources


@server.resource(
    "hevy://user",
    name="user-profile",
    description="Authenticated Hevy user profile",
    mime_type="application/json",
)
def user_resource() -> str:
    def run(api) -> str:
        return json.dumps(api.get_user_info())

    return _call(run)


@server.resource(
    "hevy://workout-count",
    name="workout-count",
    description="Total number of workouts in the Hevy account",
    mime_type="application/json",
)
def workout_count_resource() -> str:
    def run(api) -> str:
        return json.dumps({"workout_count": api.get_workout_count()})

    return _call(run)


@server.resource(
    "hevy://exercise-templates",
    name="exercise-templates",
    description="Full formatted Hevy exercise template catalog",
    mime_type="application/json",
)
def exercise_templates_resource() -> str:
    def run(api) -> str:
        return json.dumps([formatters.project_exercise_template(item) for item in _exercise_catalog(api)])

    return _call(run)


@server.resource(
    "hevy://routine-folders",
    name="routine-folders",
    description="Full formatted list of Hevy routine folders",
    mime_type="application/json",
)
def routine_folders_resource() -> str:
    def run(api) -> str:
        folders: list[dict[str, Any]] = []
        page = 1
        while True:
            data = api.list_routine_folders(page=page, page_size=10)
            batch = [item for item in data.get("routine_folders") or [] if isinstance(item, dict)]
            folders.extend(batch)
            page_count = data.get("page_count")
            if not isinstance(page_count, int) or page >= page_count or not batch:
                break
            page += 1
        return json.dumps([formatters.project_routine_folder(item) for item in folders])

    return _call(run)


# ----------------------------------------------------------------- prompts


@server.prompt(
    name="analyze-workout-progress",
    title="Analyze Workout Progress",
    description="Analyze recent workout and body-measurement trends.",
)
def analyze_workout_progress(weeks: int = 4) -> str:
    return "\n".join(
        [
            f"Analyze my workout progress over the last {weeks} weeks.",
            "Call get-training-summary with the requested weeks; it combines recent workouts and body measurements into one compact evidence set.",
            "Use the returned period, workout frequency, volume, exercise variety, session list, and measurement trend fields rather than issuing separate count and pagination calls.",
            "Base the analysis on retrieved evidence and discuss workout frequency, training volume, exercise variety, consistency, and body-measurement trends.",
            "Distinguish observations from suggestions, note missing or limited data, and do not make unsupported claims or medical conclusions.",
        ]
    )


@server.prompt(
    name="create-workout-from-routine",
    title="Create Workout From Routine",
    description="Create a completed workout from an existing routine.",
)
def create_workout_from_routine(routine_id: str | None = None, start_time: str | None = None) -> str:
    if not routine_id or not start_time:
        return "Provide a routine_id and start_time to generate the full prompt."
    return "\n".join(
        [
            f"Create a workout from routine {routine_id}, starting at {start_time}.",
            "First call get-routine with the routine_id and map supported plan fields: routine title to workout title, plus each exercise_template_id, superset_id, exercise notes, and set type.",
            "Do not copy routine-only rest_seconds or rep_range fields into create-workout.",
            "Before calling create-workout, confirm or collect the user's actual completed set data for every set, including applicable weight_kg, reps, distance_meters, duration_seconds, rpe, or custom_metric values.",
            "Also collect the required end_time in strict UTC YYYY-MM-DDTHH:mm:ssZ format and confirm any other missing required workout fields.",
            "Never invent completion data. If the actual results or end_time are unavailable, ask the user for them instead of creating the workout.",
            "Once confirmed, call create-workout with only fields supported by that tool.",
        ]
    )


def create_mcp_app():
    """Return the Streamable HTTP ASGI app, mounted at ``/mcp`` by the host."""
    app = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )
    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(NormalizeEmptyPathMiddleware)
    return app
