import logging
from typing import Any

from fastapi import APIRouter, Cookie, HTTPException, Query

from app.clients.hevy import HevyError
from app.core.config import settings
from app.core.security import get_hevy_client
from app.schemas.hevy import HevyWorkoutsResponse
from app.services.demo_data import load_sample_data
from app.services.workout_cache import (
    api_key_account_key,
    get_cached_workout_count,
    get_cached_workouts,
    is_workout_sync_complete,
    mark_workout_sync,
    oauth_account_key,
    should_sync_workouts,
    store_workouts,
)


router = APIRouter()
OAUTH_UPSTREAM_WORKOUT_PAGE_SIZE = 5
API_KEY_UPSTREAM_WORKOUT_PAGE_SIZE = 10
DEFAULT_WORKOUT_RESPONSE_LIMIT = 50
MAX_WORKOUT_RESPONSE_LIMIT = 200
MAX_WORKOUT_SYNC_PAGES = 2000


@router.get("/workouts", response_model=HevyWorkoutsResponse, tags=["Workouts"])
def get_workouts(
    hevy_access_token: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
    hevy_session_id: str | None = Cookie(None),
    offset: int = Query(0, ge=0, description="Cached workout offset - for OAuth2 mode"),
    limit: int = Query(DEFAULT_WORKOUT_RESPONSE_LIMIT, ge=1, le=MAX_WORKOUT_RESPONSE_LIMIT, description="Cached workouts per response"),
    username: str | None = Query(None, description="Filter by username - for OAuth2 mode"),
    page: int = Query(1, ge=1, description="Page number - for api-key mode"),
    page_size: int = Query(DEFAULT_WORKOUT_RESPONSE_LIMIT, ge=1, le=MAX_WORKOUT_RESPONSE_LIMIT, description="Cached workouts per response - for api-key mode"),
    start_epoch: int | None = Query(None, ge=0, description="Only workouts starting at/after this epoch (seconds)"),
    end_epoch: int | None = Query(None, ge=0, description="Only workouts starting before this epoch (seconds)"),
    name: str | None = Query(None, description="Case-insensitive workout title contains filter"),
):
    """
    Get paginated workout history.

    **OAuth2 mode (Bearer token):**
    - **offset**: Cached workout offset
    - **limit**: Cached workouts per response
    - **username**: Username filter (required)

    **API-key mode:**
    - **page**: Page number (default: 1)
    - **page_size**: Cached workouts per response

    Requires authentication cookie (OAuth2 token or API key).
    """
    if settings.demo_mode:
        if offset == 0 and page == 1:
            return load_sample_data("user_workouts_paged.json")
        return {"workouts": []}

    try:
        if hevy_api_key:
            client = get_hevy_client(api_key_cookie=hevy_api_key)
            page_offset = (page - 1) * page_size
            account_key = api_key_account_key(hevy_api_key)
            if should_sync_workouts(
                source="api_key",
                account_key=account_key,
                requested_offset=page_offset,
                requested_limit=page_size,
            ):
                _sync_api_key_workouts(client=client, account_key=account_key)

            total_count = get_cached_workout_count(
                source="api_key",
                account_key=account_key,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                name=name,
            )
            cached_workouts = get_cached_workouts(
                source="api_key",
                account_key=account_key,
                offset=page_offset,
                limit=page_size,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                name=name,
            )
            workouts = {
                "workouts": cached_workouts,
                "page": page,
                "page_size": page_size,
                "workout_count": total_count,
                "total_count": total_count,
            }
        else:
            if not username:
                raise HTTPException(status_code=400, detail="username parameter is required for OAuth2 mode")

            client = get_hevy_client(
                access_token_cookie=hevy_access_token,
                session_id_cookie=hevy_session_id,
            )

            account_key = oauth_account_key(username)
            if should_sync_workouts(
                source="oauth",
                account_key=account_key,
                requested_offset=offset,
                requested_limit=limit,
            ):
                _sync_oauth_workouts(client=client, username=username, account_key=account_key)

            total_count = get_cached_workout_count(
                source="oauth",
                account_key=account_key,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                name=name,
            )
            workouts = {
                "workouts": get_cached_workouts(
                    source="oauth",
                    account_key=account_key,
                    offset=offset,
                    limit=limit,
                    start_epoch=start_epoch,
                    end_epoch=end_epoch,
                    name=name,
                ),
                "total_count": total_count,
            }

        return workouts

    except HevyError as e:
        logging.error(f"Error fetching workouts: {e}")
        status_code = 401 if "Unauthorized" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=str(e))


def _sync_oauth_workouts(*, client: Any, username: str, account_key: str) -> None:
    source = "oauth"
    stop_on_existing = is_workout_sync_complete(source=source, account_key=account_key)
    workout_count = _workout_count_or_none(client=client, username=username)
    page_limit = _sync_page_limit(workout_count=workout_count, page_size=OAUTH_UPSTREAM_WORKOUT_PAGE_SIZE)

    for page_index in range(page_limit):
        offset = page_index * OAUTH_UPSTREAM_WORKOUT_PAGE_SIZE
        response = client.get_workouts(username=username, offset=offset)
        workouts = _workouts_from_response(response)
        found_existing = store_workouts(source=source, account_key=account_key, workouts=workouts)

        if not workouts:
            mark_workout_sync(source=source, account_key=account_key, fully_synced=True)
            return
        if stop_on_existing and found_existing:
            mark_workout_sync(source=source, account_key=account_key, fully_synced=True)
            return

    mark_workout_sync(source=source, account_key=account_key, fully_synced=workout_count is not None)


def _sync_api_key_workouts(*, client: Any, account_key: str) -> None:
    source = "api_key"
    stop_on_existing = is_workout_sync_complete(source=source, account_key=account_key)
    workout_count = _workout_count_or_none(client=client)
    page_limit = _sync_page_limit(workout_count=workout_count, page_size=API_KEY_UPSTREAM_WORKOUT_PAGE_SIZE)

    for page in range(1, page_limit + 1):
        response = client.get_workouts(page=page, page_size=API_KEY_UPSTREAM_WORKOUT_PAGE_SIZE)
        workouts = _workouts_from_response(response)
        found_existing = store_workouts(source=source, account_key=account_key, workouts=workouts)

        if not workouts:
            mark_workout_sync(source=source, account_key=account_key, fully_synced=True)
            return
        if stop_on_existing and found_existing:
            mark_workout_sync(source=source, account_key=account_key, fully_synced=True)
            return

    mark_workout_sync(source=source, account_key=account_key, fully_synced=workout_count is not None)


def _workout_count_or_none(*, client: Any, username: str | None = None) -> int | None:
    try:
        if username is not None:
            return client.get_workout_count(username=username)
        return client.get_workout_count()
    except HevyError as e:
        logging.warning(f"Workout count unavailable; falling back to empty-page sync: {e}")
        return None


def _sync_page_limit(*, workout_count: int | None, page_size: int) -> int:
    if workout_count is None:
        return MAX_WORKOUT_SYNC_PAGES
    if workout_count <= 0:
        return 0
    return min(MAX_WORKOUT_SYNC_PAGES, (workout_count + page_size - 1) // page_size)


def _workouts_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    workouts = response.get("workouts")
    if not isinstance(workouts, list):
        return []
    return [dict(workout) for workout in workouts if isinstance(workout, dict)]
