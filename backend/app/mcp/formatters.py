"""Projections from Hevy API payloads to the compact MCP contract.

Mirrors ``hevy-mcp``'s ``protocol/formatters.ts`` so tool output has the same
shape as the reference server.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


JsonDict = dict[str, Any]


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _int(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    return int(number)


def get_superset_id(exercise: JsonDict) -> int | None:
    """Read either Hevy spelling: ``superset_id`` (public) or ``supersets_id``."""
    if "superset_id" in exercise:
        return _int(exercise.get("superset_id"))
    return _int(exercise.get("supersets_id"))


def calculate_duration(start_time: Any, end_time: Any) -> str:
    if not start_time or not end_time:
        return "Unknown duration"

    try:
        start = _parse_time(start_time)
        end = _parse_time(end_time)
    except (TypeError, ValueError):
        return "Unknown duration"

    if start is None or end is None:
        return "Unknown duration"

    duration_ms = int(end.timestamp() * 1000) - int(start.timestamp() * 1000)
    if duration_ms < 0:
        return "Invalid duration (end time before start time)"

    hours, remainder = divmod(duration_ms // 1000, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _optional(target: JsonDict, source: JsonDict, key: str, output_key: str | None = None) -> None:
    value = source.get(key)
    if value is not None:
        target[output_key or key] = value


def project_workout_set(set_data: JsonDict) -> JsonDict:
    projected: JsonDict = {}
    _optional(projected, set_data, "index")
    _optional(projected, set_data, "type")
    for key in ("weight_kg", "reps", "distance_meters", "duration_seconds", "rpe", "custom_metric"):
        _optional(projected, set_data, key)
    return projected


def project_workout_exercise(exercise: JsonDict) -> JsonDict:
    projected: JsonDict = {}
    _optional(projected, exercise, "index")
    _optional(projected, exercise, "title")
    _optional(projected, exercise, "exercise_template_id")
    _optional(projected, exercise, "notes")
    superset_id = get_superset_id(exercise)
    if superset_id is not None:
        projected["supersets_id"] = superset_id
    sets = exercise.get("sets")
    if isinstance(sets, list):
        projected["sets"] = [project_workout_set(item) for item in sets if isinstance(item, dict)]
    return projected


def project_workout(workout: JsonDict) -> JsonDict:
    projected: JsonDict = {"duration": calculate_duration(workout.get("start_time"), workout.get("end_time"))}
    for key in ("id", "routine_id", "title", "description", "start_time", "end_time", "created_at", "updated_at"):
        _optional(projected, workout, key)
    exercises = workout.get("exercises")
    if isinstance(exercises, list):
        projected["exercises"] = [project_workout_exercise(item) for item in exercises if isinstance(item, dict)]
    return projected


def summarize_workout(workout: JsonDict) -> JsonDict:
    exercises = workout.get("exercises")
    exercise_list = [item for item in exercises if isinstance(item, dict)] if isinstance(exercises, list) else []
    summary: JsonDict = {
        "duration": calculate_duration(workout.get("start_time"), workout.get("end_time")),
        "exercise_count": len(exercise_list),
        "set_count": sum(len(item.get("sets") or []) for item in exercise_list if isinstance(item.get("sets"), list)),
    }
    for key in ("id", "title", "start_time", "end_time"):
        _optional(summary, workout, key)
    return summary


def project_routine_set(set_data: JsonDict) -> JsonDict:
    projected = project_workout_set(set_data)
    rep_range = set_data.get("rep_range")
    if isinstance(rep_range, dict):
        normalized = {}
        if rep_range.get("start") is not None:
            normalized["start"] = rep_range["start"]
        if rep_range.get("end") is not None:
            normalized["end"] = rep_range["end"]
        if normalized:
            projected["rep_range"] = normalized
    return projected


def project_routine_exercise(exercise: JsonDict) -> JsonDict:
    projected: JsonDict = {}
    _optional(projected, exercise, "title")
    _optional(projected, exercise, "index")
    _optional(projected, exercise, "exercise_template_id")
    _optional(projected, exercise, "notes")
    superset_id = get_superset_id(exercise)
    if superset_id is not None:
        projected["supersets_id"] = superset_id
    _optional(projected, exercise, "rest_seconds")
    sets = exercise.get("sets")
    if isinstance(sets, list):
        projected["sets"] = [project_routine_set(item) for item in sets if isinstance(item, dict)]
    return projected


def project_routine(routine: JsonDict) -> JsonDict:
    projected: JsonDict = {}
    for key in ("id", "title", "folder_id", "created_at", "updated_at"):
        _optional(projected, routine, key)
    exercises = routine.get("exercises")
    if isinstance(exercises, list):
        projected["exercises"] = [project_routine_exercise(item) for item in exercises if isinstance(item, dict)]
    return projected


def summarize_routine(routine: JsonDict) -> JsonDict:
    exercises = routine.get("exercises")
    exercise_list = [item for item in exercises if isinstance(item, dict)] if isinstance(exercises, list) else []
    summary: JsonDict = {
        "exercise_count": len(exercise_list),
        "set_count": sum(len(item.get("sets") or []) for item in exercise_list if isinstance(item.get("sets"), list)),
    }
    for key in ("id", "title", "folder_id", "updated_at"):
        _optional(summary, routine, key)
    return summary


def project_routine_folder(folder: JsonDict) -> JsonDict:
    return {
        "id": folder.get("id"),
        "title": folder.get("title"),
        "created_at": folder.get("created_at"),
        "updated_at": folder.get("updated_at"),
    }


def project_exercise_template(template: JsonDict) -> JsonDict:
    projected: JsonDict = {}
    for key in ("id", "title", "type", "primary_muscle_group", "is_custom"):
        _optional(projected, template, key)
    secondary = template.get("secondary_muscle_groups")
    if isinstance(secondary, list):
        projected["secondary_muscle_groups"] = secondary
    return projected


def normalize_exercise_history_entry(entry: JsonDict) -> JsonDict:
    projected: JsonDict = {}
    for key in (
        "workout_id",
        "workout_title",
        "workout_start_time",
        "workout_end_time",
        "exercise_template_id",
        "weight_kg",
        "reps",
        "distance_meters",
        "duration_seconds",
        "rpe",
        "custom_metric",
        "set_type",
    ):
        _optional(projected, entry, key)
    return projected


def normalize_body_measurement(measurement: JsonDict) -> JsonDict:
    projected: JsonDict = {"date": measurement.get("date")}
    for key in (
        "weight_kg",
        "lean_mass_kg",
        "fat_percent",
        "neck_cm",
        "shoulder_cm",
        "chest_cm",
        "left_bicep_cm",
        "right_bicep_cm",
        "left_forearm_cm",
        "right_forearm_cm",
        "abdomen",
        "waist",
        "hips",
    ):
        _optional(projected, measurement, key)
    for source_key, output_key in (
        ("left_thigh", "left_thigh_cm"),
        ("right_thigh", "right_thigh_cm"),
        ("left_calf", "left_calf_cm"),
        ("right_calf", "right_calf_cm"),
    ):
        _optional(projected, measurement, source_key, output_key)
    return projected


def project_workout_event(event: JsonDict) -> JsonDict:
    event_type = event.get("type")
    if event_type == "updated":
        workout = event.get("workout")
        return {
            "type": "updated",
            "workout": project_workout(workout) if isinstance(workout, dict) else None,
        }
    if event_type == "deleted":
        projected: JsonDict = {"type": "deleted", "id": event.get("id")}
        _optional(projected, event, "deleted_at")
        return projected
    return dict(event)
