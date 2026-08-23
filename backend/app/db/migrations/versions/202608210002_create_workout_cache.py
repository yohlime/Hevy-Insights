"""create workout cache

Revision ID: 202608210002
Revises: 202608210001
Create Date: 2026-08-21 00:00:02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202608210002"
down_revision: str | None = "202608210001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("workouts"):
        op.create_table(
            "workouts",
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("account_key", sa.String(), nullable=False),
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("routine_id", sa.String(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("start_time", sa.String(), nullable=True),
            sa.Column("end_time", sa.String(), nullable=True),
            sa.Column("updated_at", sa.String(), nullable=True),
            sa.Column("created_at", sa.String(), nullable=True),
            sa.Column("exercises", sa.JSON(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("start_time_epoch", sa.Integer(), nullable=True),
            sa.Column("updated_at_epoch", sa.Integer(), nullable=True),
            sa.Column("synced_at", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("source", "account_key", "id"),
        )
        op.create_index("ix_workouts_account_start_time", "workouts", ["source", "account_key", "start_time_epoch"])

    if not inspector.has_table("workout_exercises"):
        op.create_table(
            "workout_exercises",
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("account_key", sa.String(), nullable=False),
            sa.Column("workout_id", sa.String(), nullable=False),
            sa.Column("exercise_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("exercise_template_id", sa.String(), nullable=True),
            sa.Column("supersets_id", sa.Integer(), nullable=True),
            sa.Column("sets", sa.JSON(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("synced_at", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("source", "account_key", "workout_id", "exercise_index"),
        )
        op.create_index(
            "ix_workout_exercises_template",
            "workout_exercises",
            ["source", "account_key", "exercise_template_id"],
        )

    if not inspector.has_table("workout_syncs"):
        op.create_table(
            "workout_syncs",
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("account_key", sa.String(), nullable=False),
            sa.Column("fully_synced", sa.Boolean(), nullable=False),
            sa.Column("synced_at", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("source", "account_key"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("workout_exercises"):
        index_names = {index["name"] for index in inspector.get_indexes("workout_exercises")}
        if "ix_workout_exercises_template" in index_names:
            op.drop_index("ix_workout_exercises_template", table_name="workout_exercises")
        op.drop_table("workout_exercises")
    if inspector.has_table("workout_syncs"):
        op.drop_table("workout_syncs")
    if inspector.has_table("workouts"):
        index_names = {index["name"] for index in inspector.get_indexes("workouts")}
        if "ix_workouts_account_start_time" in index_names:
            op.drop_index("ix_workouts_account_start_time", table_name="workouts")
        op.drop_table("workouts")
