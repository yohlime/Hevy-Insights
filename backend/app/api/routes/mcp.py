from typing import Any

from fastapi import APIRouter, Cookie, HTTPException


router = APIRouter()


@router.get("/mcp/token", tags=["MCP"])
def mcp_token(
    hevy_session_id: str | None = Cookie(None),
    hevy_api_key: str | None = Cookie(None),
) -> dict[str, Any]:
    """Return the credential an MCP client should use for this web session.

    OAuth sessions return the long-lived ``hevy_session_id``; PRO API-key
    sessions return the API key. Both are already available to the
    authenticated browser through HttpOnly cookies.
    """
    if hevy_session_id:
        return {
            "mode": "oauth",
            "token": hevy_session_id,
            "header": "Authorization",
            "value": f"Bearer {hevy_session_id}",
        }

    if hevy_api_key:
        return {
            "mode": "api_key",
            "token": hevy_api_key,
            "header": "api-key",
            "value": hevy_api_key,
        }

    raise HTTPException(status_code=401, detail="Not authenticated")
