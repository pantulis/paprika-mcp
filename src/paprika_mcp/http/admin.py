"""A minimal, secret-gated admin endpoint for registering OAuth clients.

Exists because Render's free plan supports neither `render ssh` nor one-off
Jobs (both return "new paid services not allowed" / require a paid plan),
and the free Key Value instance rejects external connections -- so there is
no way to reach `Store.create_client` from outside the running web service
except through the web service itself. `paprika-mcp register-client` (the
CLI command, see __main__.py) still exists and remains the preferred path
for local development and any deployment target that *does* offer shell
access; this endpoint is the fallback for Render's free plan specifically.

Gated by `ADMIN_SECRET`, a secret distinct from `MCP_PASSPHRASE` -- the two
guard different things (one-time client provisioning vs. every end-user
authorization) and shouldn't share a security boundary. If `ADMIN_SECRET`
isn't set, this endpoint doesn't exist at all (404), rather than existing
unguarded.
"""

from __future__ import annotations

import secrets
import time

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import Config
from .store import Store

# Same lightweight in-memory rate limit pattern as /authorize's passphrase
# check (see oauth.py) -- resets on process restart, fine for a personal,
# low-traffic admin endpoint.
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_failed_attempts: list[float] = []


def _rate_limited() -> bool:
    now = time.time()
    while _failed_attempts and now - _failed_attempts[0] >= _WINDOW_SECONDS:
        _failed_attempts.pop(0)
    return len(_failed_attempts) >= _MAX_ATTEMPTS


def _record_failure() -> None:
    _failed_attempts.append(time.time())


async def register_client(request: Request) -> Response:
    config: Config = request.app.state.config
    store: Store = request.app.state.store

    if not config.admin_secret:
        return JSONResponse({"error": "not_found"}, status_code=404)

    if _rate_limited():
        return JSONResponse({"error": "rate_limited"}, status_code=429)

    provided = request.headers.get("x-admin-secret", "")
    if not secrets.compare_digest(provided, config.admin_secret):
        _record_failure()
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    redirect_uri = body.get("redirect_uri")
    if not redirect_uri:
        return JSONResponse(
            {
                "error": "invalid_request",
                "error_description": "redirect_uri is required",
            },
            status_code=400,
        )
    client_name = body.get("name") or "Client"

    client_id = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)
    await store.create_client(client_id, client_secret, client_name, redirect_uri)

    return JSONResponse(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_name,
            "redirect_uri": redirect_uri,
        }
    )
