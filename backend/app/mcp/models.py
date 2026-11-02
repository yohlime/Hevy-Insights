"""Input models mirroring hevy-mcp's canonical snake_case schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SetType = Literal["warmup", "normal", "failure", "dropset"]
MuscleGroup = Literal[
    "abdominals",
    "shoulders",
    "biceps",
    "triceps",
    "forearms",
    "quadriceps",
    "hamstrings",
    "calves",
    "glutes",
    "abductors",
    "adductors",
    "lats",
    "upper_back",
    "traps",
    "lower_back",
    "chest",
    "cardio",
    "neck",
    "full_body",
    "other",
]
ExerciseType = Literal[
    "weight_reps",
    "reps_only",
    "bodyweight_reps",
    "bodyweight_assisted_reps",
    "duration",
    "weight_duration",
    "distance_duration",
    "short_distance_weight",
]
EquipmentCategory = Literal[
    "none",
    "barbell",
    "dumbbell",
    "kettlebell",
    "machine",
    "plate",
    "resistance_band",
    "suspension",
    "other",
]

UTC_TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
CALENDAR_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepRange(StrictModel):
    start: int | None = None
    end: int | None = None


class WorkoutSetInput(StrictModel):
    type: SetType = "normal"
    weight_kg: float | None = None
    reps: int | None = None
    distance_meters: int | None = None
    duration_seconds: int | None = None
    rpe: float | None = None
    custom_metric: float | None = None


class WorkoutExerciseInput(StrictModel):
    exercise_template_id: str = Field(min_length=1)
    superset_id: int | None = None
    notes: str | None = None
    sets: list[WorkoutSetInput]


class WorkoutPayload(StrictModel):
    title: str = Field(min_length=1)
    description: str | None = None
    start_time: str = Field(pattern=UTC_TIMESTAMP_PATTERN)
    end_time: str = Field(pattern=UTC_TIMESTAMP_PATTERN)
    is_private: bool = False
    exercises: list[WorkoutExerciseInput]


class WorkoutMetadataPatch(StrictModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    start_time: str | None = Field(default=None, pattern=UTC_TIMESTAMP_PATTERN)
    end_time: str | None = Field(default=None, pattern=UTC_TIMESTAMP_PATTERN)
    is_private: bool


class ReplaceWorkoutExercisesPayload(StrictModel):
    is_private: bool
    exercises: list[WorkoutExerciseInput]


class RoutineSetInput(StrictModel):
    type: SetType = "normal"
    weight_kg: float | None = None
    reps: int | None = None
    distance_meters: int | None = None
    duration_seconds: int | None = None
    rep_range: RepRange | None = None
    custom_metric: float | None = None


class RoutineExerciseInput(StrictModel):
    exercise_template_id: str = Field(min_length=1)
    superset_id: int | None = None
    rest_seconds: int | None = Field(default=None, ge=0)
    notes: str | None = None
    sets: list[RoutineSetInput] = Field(min_length=1)


class RoutinePayload(StrictModel):
    title: str = Field(min_length=1)
    folder_id: int | None = None
    notes: str | None = None
    exercises: list[RoutineExerciseInput] = Field(min_length=1)


class RoutineUpdatePayload(StrictModel):
    title: str = Field(min_length=1)
    notes: str | None = None
    exercises: list[RoutineExerciseInput] = Field(min_length=1)


class RoutineFolderPayload(StrictModel):
    title: str = Field(min_length=1)


class ExerciseTemplatePayload(StrictModel):
    title: str = Field(min_length=1)
    exercise_type: ExerciseType
    equipment_category: EquipmentCategory
    muscle_group: MuscleGroup
    other_muscles: list[MuscleGroup] = Field(default_factory=list)



