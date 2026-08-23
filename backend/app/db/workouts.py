from sqlalchemy import JSON, Boolean, Column, Index, Integer, String, Table

from app.core.database import metadata


workouts_table = Table(
    "workouts",
    metadata,
    Column("source", String, primary_key=True),
    Column("account_key", String, primary_key=True),
    Column("id", String, primary_key=True),
    Column("title", String, nullable=True),
    Column("routine_id", String, nullable=True),
    Column("description", String, nullable=True),
    Column("start_time", String, nullable=True),
    Column("end_time", String, nullable=True),
    Column("updated_at", String, nullable=True),
    Column("created_at", String, nullable=True),
    Column("exercises", JSON, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("start_time_epoch", Integer, nullable=True),
    Column("updated_at_epoch", Integer, nullable=True),
    Column("synced_at", String, nullable=False),
)

workout_exercises_table = Table(
    "workout_exercises",
    metadata,
    Column("source", String, primary_key=True),
    Column("account_key", String, primary_key=True),
    Column("workout_id", String, primary_key=True),
    Column("exercise_index", Integer, primary_key=True),
    Column("title", String, nullable=True),
    Column("notes", String, nullable=True),
    Column("exercise_template_id", String, nullable=True),
    Column("supersets_id", Integer, nullable=True),
    Column("sets", JSON, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("synced_at", String, nullable=False),
)

workout_syncs_table = Table(
    "workout_syncs",
    metadata,
    Column("source", String, primary_key=True),
    Column("account_key", String, primary_key=True),
    Column("fully_synced", Boolean, nullable=False),
    Column("synced_at", String, nullable=False),
)

Index("ix_workouts_account_start_time", workouts_table.c.source, workouts_table.c.account_key, workouts_table.c.start_time_epoch)
Index(
    "ix_workout_exercises_template",
    workout_exercises_table.c.source,
    workout_exercises_table.c.account_key,
    workout_exercises_table.c.exercise_template_id,
)
