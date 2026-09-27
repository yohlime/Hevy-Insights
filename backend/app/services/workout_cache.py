from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Literal

from sqlalchemy import delete, desc, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.database import engine
from app.db.workouts import workout_exercises_table, workout_syncs_table, workouts_table


JsonDict = dict[str, Any]
WorkoutSource = Literal["oauth", "api_key"]


def oauth_account_key(username: str) -> str:
    return username.strip().lower()


def api_key_account_key(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()


def should_sync_workouts(*, source: WorkoutSource, account_key: str, requested_offset: int, requested_limit: int) -> bool:
    if requested_offset == 0:
        return True

    fully_synced = is_workout_sync_complete(source=source, account_key=account_key)
    cached_count = get_cached_workout_count(source=source, account_key=account_key)
    if cached_count < requested_offset + requested_limit:
        return not fully_synced

    return not fully_synced


def is_workout_sync_complete(*, source: WorkoutSource, account_key: str) -> bool:
    with engine.begin() as connection:
        row = connection.execute(
            select(workout_syncs_table.c.fully_synced).where(
                workout_syncs_table.c.source == source,
                workout_syncs_table.c.account_key == account_key,
            )
        ).one_or_none()

    return bool(row[0]) if row else False


def get_cached_workout_count(
    *,
    source: WorkoutSource,
    account_key: str,
    start_epoch: int | None = None,
    end_epoch: int | None = None,
    name: str | None = None,
) -> int:
    statement = (
        select(func.count())
        .select_from(workouts_table)
        .where(
            workouts_table.c.source == source,
            workouts_table.c.account_key == account_key,
        )
    )
    statement = _apply_workout_filters(statement, start_epoch=start_epoch, end_epoch=end_epoch, name=name)

    with engine.begin() as connection:
        count = connection.execute(statement).scalar_one()

    return int(count)


def get_cached_workouts(
    *,
    source: WorkoutSource,
    account_key: str,
    offset: int,
    limit: int,
    start_epoch: int | None = None,
    end_epoch: int | None = None,
    name: str | None = None,
) -> list[JsonDict]:
    statement = (
        select(workouts_table.c.payload)
        .where(
            workouts_table.c.source == source,
            workouts_table.c.account_key == account_key,
        )
        .order_by(
            desc(workouts_table.c.start_time_epoch),
            desc(workouts_table.c.updated_at_epoch),
            desc(workouts_table.c.id),
        )
        .offset(offset)
        .limit(limit)
    )
    statement = _apply_workout_filters(statement, start_epoch=start_epoch, end_epoch=end_epoch, name=name)

    with engine.begin() as connection:
        rows = connection.execute(statement).mappings().all()

    return [dict(row["payload"]) for row in rows if isinstance(row["payload"], dict)]


def _apply_workout_filters(statement: Any, *, start_epoch: int | None, end_epoch: int | None, name: str | None) -> Any:
    if start_epoch is not None:
        statement = statement.where(workouts_table.c.start_time_epoch >= start_epoch)
    if end_epoch is not None:
        statement = statement.where(workouts_table.c.start_time_epoch < end_epoch)
    if name:
        statement = statement.where(workouts_table.c.title.ilike(f"%{name.strip()}%"))
    return statement


def store_workouts(*, source: WorkoutSource, account_key: str, workouts: list[JsonDict]) -> bool:
    now = _now_iso()
    workout_rows = [_workout_row(source, account_key, workout, now) for workout in workouts]
    workout_rows = [row for row in workout_rows if row is not None]
    workout_ids = [str(row["id"]) for row in workout_rows]
    exercise_rows = [
        exercise_row
        for workout in workouts
        for exercise_row in _exercise_rows(source=source, account_key=account_key, workout=workout, now=now)
    ]

    with engine.begin() as connection:
        existing_ids = set(
            connection.execute(
                select(workouts_table.c.id).where(
                    workouts_table.c.source == source,
                    workouts_table.c.account_key == account_key,
                    workouts_table.c.id.in_(workout_ids),
                )
            ).scalars()
        )

        if workout_rows:
            upsert = sqlite_insert(workouts_table).values(workout_rows)
            connection.execute(
                upsert.on_conflict_do_update(
                    index_elements=["source", "account_key", "id"],
                    set_={
                        "title": upsert.excluded.title,
                        "routine_id": upsert.excluded.routine_id,
                        "description": upsert.excluded.description,
                        "start_time": upsert.excluded.start_time,
                        "end_time": upsert.excluded.end_time,
                        "updated_at": upsert.excluded.updated_at,
                        "created_at": upsert.excluded.created_at,
                        "exercises": upsert.excluded.exercises,
                        "payload": upsert.excluded.payload,
                        "start_time_epoch": upsert.excluded.start_time_epoch,
                        "updated_at_epoch": upsert.excluded.updated_at_epoch,
                        "synced_at": upsert.excluded.synced_at,
                    },
                )
            )

            connection.execute(
                delete(workout_exercises_table).where(
                    workout_exercises_table.c.source == source,
                    workout_exercises_table.c.account_key == account_key,
                    workout_exercises_table.c.workout_id.in_(workout_ids),
                )
            )

        if exercise_rows:
            connection.execute(insert(workout_exercises_table), exercise_rows)

    return bool(existing_ids)


def mark_workout_sync(*, source: WorkoutSource, account_key: str, fully_synced: bool) -> None:
    now = _now_iso()
    with engine.begin() as connection:
        upsert = sqlite_insert(workout_syncs_table).values(
            source=source,
            account_key=account_key,
            fully_synced=fully_synced,
            synced_at=now,
        )
        connection.execute(
            upsert.on_conflict_do_update(
                index_elements=["source", "account_key"],
                set_={
                    "fully_synced": upsert.excluded.fully_synced,
                    "synced_at": upsert.excluded.synced_at,
                },
            )
        )


def _workout_row(source: WorkoutSource, account_key: str, workout: JsonDict, now: str) -> JsonDict | None:
    workout_id = _workout_id(workout)
    if not workout_id:
        return None

    return {
        "source": source,
        "account_key": account_key,
        "id": workout_id,
        "title": _optional_str(workout.get("title")),
        "routine_id": _optional_str(workout.get("routine_id")),
        "description": _optional_str(workout.get("description")),
        "start_time": _optional_time_str(workout.get("start_time")),
        "end_time": _optional_time_str(workout.get("end_time")),
        "updated_at": _optional_time_str(workout.get("updated_at")),
        "created_at": _optional_time_str(workout.get("created_at")),
        "exercises": workout.get("exercises") if isinstance(workout.get("exercises"), list) else [],
        "payload": dict(workout),
        "start_time_epoch": _optional_int(workout.get("start_time")),
        "updated_at_epoch": _optional_int(workout.get("updated_at")),
        "synced_at": now,
    }


def _exercise_rows(*, source: WorkoutSource, account_key: str, workout: JsonDict, now: str) -> list[JsonDict]:
    workout_id = _workout_id(workout)
    exercises = workout.get("exercises")
    if not workout_id or not isinstance(exercises, list):
        return []

    rows = []
    for fallback_index, exercise in enumerate(exercises):
        if not isinstance(exercise, dict):
            continue

        rows.append(
            {
                "source": source,
                "account_key": account_key,
                "workout_id": workout_id,
                "exercise_index": _optional_int(exercise.get("index")) or fallback_index,
                "title": _optional_str(exercise.get("title")),
                "notes": _optional_str(exercise.get("notes")),
                "exercise_template_id": _optional_str(exercise.get("exercise_template_id")),
                "supersets_id": _optional_int(exercise.get("supersets_id")),
                "sets": exercise.get("sets") if isinstance(exercise.get("sets"), list) else [],
                "payload": dict(exercise),
                "synced_at": now,
            }
        )

    return rows


def _workout_id(workout: JsonDict) -> str | None:
    workout_id = workout.get("id")
    if isinstance(workout_id, str) and workout_id:
        return workout_id
    if isinstance(workout_id, int):
        return str(workout_id)
    if workout:
        return sha256(json.dumps(workout, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        if value.isdigit():
            return int(value)
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None
    return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_time_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
