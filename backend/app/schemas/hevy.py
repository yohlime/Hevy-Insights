from pydantic import BaseModel, ConfigDict, Field


class HevyUser(BaseModel):
    """User data returned from Hevy API login."""

    access_token: str
    user_id: str
    username: str | None = None
    email: str | None = None
    refresh_token: str | None = None
    expires_at: str | int | float | None = None


class HevyWorkoutSet(BaseModel):
    """Set data from Hevy's Workout schema."""

    model_config = ConfigDict(extra="allow")

    index: int | float | None = None
    type: str | None = None
    weight_kg: float | None = None
    reps: float | None = None
    distance_meters: float | None = None
    duration_seconds: float | None = None
    rpe: float | None = None
    custom_metric: float | None = None


class HevyWorkoutExercise(BaseModel):
    """Exercise data from Hevy's Workout schema."""

    model_config = ConfigDict(extra="allow")

    index: int | float | None = None
    title: str | None = None
    notes: str | None = None
    exercise_template_id: str | None = None
    supersets_id: int | float | None = None
    sets: list[HevyWorkoutSet] = Field(default_factory=list)


class HevyWorkout(BaseModel):
    """Workout data returned by Hevy's workouts endpoints."""

    model_config = ConfigDict(extra="allow")

    id: str | int | None = None
    title: str | None = None
    routine_id: str | None = None
    description: str | None = None
    start_time: str | int | float | None = None
    end_time: str | int | float | None = None
    updated_at: str | int | float | None = None
    created_at: str | int | float | None = None
    exercises: list[HevyWorkoutExercise] = Field(default_factory=list)


class HevyWorkoutsResponse(BaseModel):
    """Paginated workout response normalized by the backend for frontend use."""

    model_config = ConfigDict(extra="allow")

    workouts: list[HevyWorkout]
    page: int | None = None
    page_count: int | None = None
    page_size: int | None = None
    workout_count: int | None = None
