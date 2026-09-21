"""Starlette ASGI app: OAuth authorization server + the /mcp Streamable HTTP
endpoint.

Run with `paprika-mcp serve` (see __main__.py) or directly via
`uvicorn paprika_mcp.http.app:create_app --factory`.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from ..server import app as mcp_server
from .auth_middleware import BearerAuthMiddleware
from .config import Config
from .oauth import (
    authorization_server_metadata,
    authorize,
    protected_resource_metadata,
    token,
)
from .store import Store

logger = logging.getLogger(__name__)


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app() -> ASGIApp:
    config = Config.from_env()
    store = Store(config.db_path)

    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=True,
        stateless=True,
    )

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info(
                "paprika-mcp HTTP server starting (base_url=%s)", config.base_url
            )
            yield
            logger.info("paprika-mcp HTTP server shutting down")

    starlette_app = Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/.well-known/oauth-protected-resource", protected_resource_metadata),
            Route(
                "/.well-known/oauth-protected-resource/mcp", protected_resource_metadata
            ),
            Route(
                "/.well-known/oauth-authorization-server", authorization_server_metadata
            ),
            Route("/authorize", authorize, methods=["GET", "POST"]),
            Route("/token", token, methods=["POST"]),
            Mount("/mcp", app=handle_mcp),
        ],
        lifespan=lifespan,
    )
    starlette_app.state.config = config
    starlette_app.state.store = store

    # Only /mcp is gated; /authorize, /token, /.well-known/*, /healthz stay open.
    return BearerAuthMiddleware(starlette_app, config)
