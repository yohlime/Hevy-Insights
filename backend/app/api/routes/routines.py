import logging
from typing import Any

from fastapi import APIRouter, Cookie, HTTPException

from app.clients.hevy import HevyError, HevyOAuthClient
from app.core.config import settings
from app.core.security import get_hevy_client
from app.schemas.routines import (
    CreateRoutineFolderRequest,
    CreateRoutineRequest,
    RoutineDetailResponse,
    RoutineFolderResponse,
    RoutineFolderMutationResponse,
    RoutineMutationResponse,
    RoutineResponse,
    UpdateRoutineFolderRequest,
)


router = APIRouter()


@router.post("/routine_folders", response_model=RoutineFolderResponse, tags=["Routines"])
def create_routine_folder(
    folder_data: CreateRoutineFolderRequest,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineFolderResponse:
    """Create a Hevy routine folder for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineFolderResponse(
            id=0,
            index=0,
            title=folder_data.folder.title,
            updated_at="2026-08-23T12:56:11.414Z",
            created_at="2026-08-23T12:56:11.414Z",
        )

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

        return RoutineFolderResponse.model_validate(client.create_routine_folder(folder_data.folder.title))

    except HevyError as e:
        logging.error(f"Error creating routine folder: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.get("/routine_folders", tags=["Routines"])
def get_routine_folders(
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> Any:
    """Get Hevy routine folders for OAuth-authenticated users."""
    if settings.demo_mode:
        return {"routine_folders": []}

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

        return client.get_routine_folders()

    except HevyError as e:
        logging.error(f"Error fetching routine folders: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.put("/routine_folders/{folder_id}", response_model=RoutineFolderMutationResponse, tags=["Routines"])
def update_routine_folder(
    folder_id: str,
    folder_data: UpdateRoutineFolderRequest,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineFolderMutationResponse:
    """Update a Hevy routine folder for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineFolderMutationResponse(folderId=folder_id, title=folder_data.title)

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

        return RoutineFolderMutationResponse.model_validate(client.update_routine_folder(folder_id, folder_data.title))

    except HevyError as e:
        logging.error(f"Error updating routine folder: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.delete("/routine_folders/{folder_id}", response_model=RoutineFolderMutationResponse, tags=["Routines"])
def delete_routine_folder(
    folder_id: str,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineFolderMutationResponse:
    """Delete a Hevy routine folder for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineFolderMutationResponse(folderId=folder_id)

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine folders require OAuth2 authentication")

        return RoutineFolderMutationResponse.model_validate(client.delete_routine_folder(folder_id))

    except HevyError as e:
        logging.error(f"Error deleting routine folder: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/routines", response_model=RoutineResponse, tags=["Routines"])
def create_routine(
    routine_data: CreateRoutineRequest,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineResponse:
    """Create a Hevy routine for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineResponse(routineId="00000000-0000-0000-0000-000000000000")

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine creation requires OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine creation requires OAuth2 authentication")

        return RoutineResponse.model_validate(client.create_routine(routine_data.routine.model_dump(mode="json")))

    except HevyError as e:
        logging.error(f"Error creating routine: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.get("/routines/{routine_id}", response_model=RoutineDetailResponse, tags=["Routines"])
def get_routine(
    routine_id: str,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineDetailResponse:
    """Get a Hevy routine for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineDetailResponse(routine={"id": routine_id, "title": "Demo routine"})

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine fetch requires OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine fetch requires OAuth2 authentication")

        return RoutineDetailResponse.model_validate(client.get_routine(routine_id))

    except HevyError as e:
        logging.error(f"Error fetching routine: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.put("/routines/{routine_id}", response_model=RoutineMutationResponse, tags=["Routines"])
def update_routine(
    routine_id: str,
    routine_data: CreateRoutineRequest,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineMutationResponse:
    """Update a Hevy routine for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineMutationResponse(routineId=routine_id)

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine updates require OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine updates require OAuth2 authentication")

        return RoutineMutationResponse.model_validate(client.update_routine(routine_id, routine_data.routine.model_dump(mode="json")))

    except HevyError as e:
        logging.error(f"Error updating routine: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


@router.delete("/routines/{routine_id}", response_model=RoutineMutationResponse, tags=["Routines"])
def delete_routine(
    routine_id: str,
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
) -> RoutineMutationResponse:
    """Delete a Hevy routine for OAuth-authenticated users."""
    if settings.demo_mode:
        return RoutineMutationResponse(routineId=routine_id)

    if hevy_api_key or hevy_access_token == "api_key_mode":
        raise HTTPException(status_code=400, detail="Routine deletion requires OAuth2 authentication")

    try:
        client = get_hevy_client(
            access_token_cookie=hevy_access_token,
            session_id_cookie=hevy_session_id,
        )
        if not isinstance(client, HevyOAuthClient):
            raise HTTPException(status_code=400, detail="Routine deletion requires OAuth2 authentication")

        return RoutineMutationResponse.model_validate(client.delete_routine(routine_id))

    except HevyError as e:
        logging.error(f"Error deleting routine: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))
