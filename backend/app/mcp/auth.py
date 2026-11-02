"""Request-scoped Hevy credentials for the MCP endpoint."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class McpCredentials:
    """Credentials supplied by an MCP client for one request.

    - ``api_key``: a Hevy PRO API key (``api-key`` / ``x-api-key`` header).
    - ``bearer``: a Hevy OAuth session id, or a raw Hevy OAuth access token.
    - ``session_id``: ``hevy_session_id`` cookie from the web app.
    """

    api_key: str | None = None
    bearer: str | None = None
    session_id: str | None = None


_credentials_var: ContextVar[McpCredentials | None] = ContextVar("hevy_mcp_credentials", default=None)


def current_credentials() -> McpCredentials:
    """Return the credentials attached to the current MCP request."""
    return _credentials_var.get() or McpCredentials()


def extract_credentials(headers: Headers) -> McpCredentials:
    api_key = (headers.get("api-key") or headers.get("x-api-key") or "").strip() or None

    authorization = headers.get("authorization", "")
    bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else None

    session_id = None
    for part in headers.get("cookie", "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == "hevy_session_id" and value:
            session_id = value
            break

    return McpCredentials(api_key=api_key, bearer=bearer or None, session_id=session_id)


class ApiKeyMiddleware:
    """Expose the caller's Hevy credentials to MCP tools and resources."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            _credentials_var.set(extract_credentials(Headers(scope=scope)))
        await self.app(scope, receive, send)


class McpTrailingSlashMiddleware:
    """Serve ``/mcp`` without a redirect (clients may not follow POST 307s)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)


class NormalizeEmptyPathMiddleware:
    """Map ``/mcp`` (empty sub-path) to the MCP app's ``/`` route.

    Starlette's ``Mount`` strips ``/mcp`` and leaves an empty path, which its
    router would normally answer with a ``/mcp/`` redirect. Some MCP clients
    do not follow POST redirects, so rewrite it before routing.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "":
            scope = dict(scope)
            scope["path"] = "/"
        await self.app(scope, receive, send)
