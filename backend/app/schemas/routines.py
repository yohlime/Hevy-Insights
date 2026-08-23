from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoutineFolderCreate(BaseModel):
    title: str = Field(..., min_length=1)


class CreateRoutineFolderRequest(BaseModel):
    folder: RoutineFolderCreate


class UpdateRoutineFolderRequest(BaseModel):
    title: str = Field(..., min_length=1)


class RoutineFolderResponse(BaseModel):
    id: int
    index: int
    title: str
    updated_at: str
    created_at: str


class RoutineSetCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    indicator: str


class RoutineExerciseCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    exercise_template_id: str
    rest_seconds: int | None = None
    sets: list[RoutineSetCreate] = Field(default_factory=list)
    notes: str | None = None


class RoutineCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str = Field(..., min_length=1)
    exercises: list[RoutineExerciseCreate] = Field(default_factory=list)
    folder_id: int | None = None
    index: int | None = 0
    program_id: int | str | None = None
    notes: str | None = None
    coach_force_rpe_enabled: bool | None = False


class CreateRoutineRequest(BaseModel):
    routine: RoutineCreate


class RoutineResponse(BaseModel):
    routineId: str


class RoutineMutationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    routineId: str | None = None


class RoutineFolderMutationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    folderId: str | None = None
    title: str | None = None


class RoutineDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    routine: dict[str, Any] | None = None
