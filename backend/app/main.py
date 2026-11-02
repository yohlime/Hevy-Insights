from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.core.config import settings
from app.core.database import run_migrations
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.mcp.auth import McpTrailingSlashMiddleware
from app.mcp.server import create_mcp_app


def create_app() -> FastAPI:
    setup_logging()
    run_migrations()

    mcp_app = create_mcp_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Starlette does not run mounted sub-app lifespans, so start the MCP
        # streamable-HTTP session manager explicitly.
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(
        title="Hevy Insights API",
        description="Backend API for Hevy Insights",
        version="1.5.2",
        docs_url="/api/docs",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, cast(Any, _rate_limit_exceeded_handler))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(McpTrailingSlashMiddleware)

    app.include_router(api_router)
    app.mount("/mcp", mcp_app)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=5000, log_level="info")
