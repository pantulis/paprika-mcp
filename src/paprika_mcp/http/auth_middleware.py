"""Bearer-token auth middleware protecting the /mcp endpoint.

Validates the JWT access tokens issued by `/token` in oauth.py. Implemented
as plain ASGI middleware rather than through the `mcp` SDK's own auth
machinery, so it doesn't depend on which major version of `mcp` this project
is pinned to (the SDK's auth API shape changed between 1.x and 2.x).

On failure, responds per RFC 9728: 401 with a `WWW-Authenticate` header
pointing at the protected-resource metadata document, so compliant clients
(including Gemini) can discover how to obtain a token.
"""

from __future__ import annotations

import jwt
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Config


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, config: Config, protected_prefix: str = "/mcp"):
        self.app = app
        self.config = config
        self.protected_prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(
            self.protected_prefix
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("latin-1")
        token = (
            auth_header[7:].strip()
            if auth_header.lower().startswith("bearer ")
            else None
        )

        error: str | None = None
        description = ""
        if not token:
            error, description = "invalid_request", "Missing bearer token"
        else:
            try:
                jwt.decode(
                    token,
                    self.config.jwt_secret,
                    algorithms=["HS256"],
                    audience=self.config.resource_url,
                    issuer=self.config.base_url,
                )
            except jwt.ExpiredSignatureError:
                error, description = "invalid_token", "Token expired"
            except jwt.InvalidTokenError:
                error, description = "invalid_token", "Invalid token"

        if error:
            resource_metadata_url = (
                f"{self.config.base_url}/.well-known/oauth-protected-resource"
            )
            www_authenticate = (
                f'Bearer error="{error}", error_description="{description}", '
                f'resource_metadata="{resource_metadata_url}"'
            )
            response = JSONResponse(
                {"error": error, "error_description": description},
                status_code=401,
                headers={"WWW-Authenticate": www_authenticate},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
