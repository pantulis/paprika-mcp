"""Minimal OAuth 2.1 authorization server for the /mcp endpoint.

Single-user, single-client by design: `/authorize` is gated by one shared
passphrase (`MCP_PASSPHRASE`) instead of a real identity system, and clients
are pre-registered via the `paprika-mcp register-client` CLI command rather
than Dynamic Client Registration.

Dynamic Client Registration is deliberately not offered (no
`registration_endpoint` in the authorization-server metadata): Gemini's
custom-app connector falls back to a manual Client ID/Secret form when DCR
isn't advertised, which is simpler and more predictable than the DCR flow,
which has documented failure modes with Gemini's connector.

PKCE (S256) is mandatory on every authorization_code grant, per OAuth 2.1.
"""

from __future__ import annotations

import base64
import hashlib
import html
import secrets
import time

import anyio
import jwt
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .config import Config
from .store import Store

# In-memory rate limit for failed passphrase attempts, keyed by client_id.
# Resets on process restart, which is acceptable for a single-user server.
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_failed_attempts: dict[str, list[float]] = {}


def _rate_limited(client_id: str) -> bool:
    now = time.time()
    attempts = [
        t for t in _failed_attempts.get(client_id, []) if now - t < _WINDOW_SECONDS
    ]
    _failed_attempts[client_id] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def _record_failure(client_id: str) -> None:
    _failed_attempts.setdefault(client_id, []).append(time.time())


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed, code_challenge)


def _basic_auth_credentials(request: Request) -> tuple[str, str] | None:
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        client_id, _, client_secret = decoded.partition(":")
        return client_id, client_secret
    except Exception:
        return None


def _issue_access_token(config: Config, client_id: str, scope: str) -> str:
    now = int(time.time())
    payload = {
        "iss": config.base_url,
        "aud": config.resource_url,
        "sub": "owner",
        "client_id": client_id,
        "scope": scope,
        "iat": now,
        "exp": now + config.access_token_ttl,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


# --------------------------------------------------------------------------
# Discovery metadata
# --------------------------------------------------------------------------


async def protected_resource_metadata(request: Request) -> Response:
    """RFC 9728 Protected Resource Metadata for the /mcp endpoint."""
    config: Config = request.app.state.config
    return JSONResponse(
        {
            "resource": config.resource_url,
            "authorization_servers": [config.base_url],
            "bearer_methods_supported": ["header"],
        }
    )


async def authorization_server_metadata(request: Request) -> Response:
    """RFC 8414 Authorization Server Metadata.

    Deliberately omits `registration_endpoint` -- see module docstring.
    Only standard keys are included: non-standard extension fields are a
    documented cause of Gemini's client silently failing discovery.
    """
    config: Config = request.app.state.config
    return JSONResponse(
        {
            "issuer": config.base_url,
            "authorization_endpoint": f"{config.base_url}/authorize",
            "token_endpoint": f"{config.base_url}/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "scopes_supported": ["paprika"],
        }
    )


# --------------------------------------------------------------------------
# /authorize
# --------------------------------------------------------------------------


def _authorize_page(
    *,
    client_name: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
    error: str | None = None,
) -> str:
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect to Paprika</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 420px;
         margin: 4rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.25rem; }}
  input[type=password] {{ width: 100%; padding: 0.6rem; font-size: 1rem;
         box-sizing: border-box; margin: 0.75rem 0; border: 1px solid #ccc;
         border-radius: 6px; }}
  button {{ width: 100%; padding: 0.6rem; font-size: 1rem; cursor: pointer;
         border-radius: 6px; border: none; background: #1a1a1a; color: #fff; }}
  .error {{ color: #b00020; }}
</style>
</head>
<body>
  <h1>Connect &ldquo;{html.escape(client_name)}&rdquo; to your Paprika recipes</h1>
  <p>Requested access: {html.escape(scope)}</p>
  {error_html}
  <form method="post">
    <input type="hidden" name="client_id" value="{html.escape(client_id)}">
    <input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri)}">
    <input type="hidden" name="state" value="{html.escape(state)}">
    <input type="hidden" name="scope" value="{html.escape(scope)}">
    <input type="hidden" name="code_challenge" value="{html.escape(code_challenge)}">
    <input type="hidden" name="code_challenge_method" value="{html.escape(code_challenge_method)}">
    <input type="password" name="passphrase" placeholder="Passphrase" autofocus required>
    <button type="submit">Authorize</button>
  </form>
</body>
</html>"""


async def authorize(request: Request) -> Response:
    config: Config = request.app.state.config
    store: Store = request.app.state.store

    if request.method == "GET":
        params = request.query_params
    else:
        params = await request.form()

    response_type = params.get("response_type", "code")
    client_id = params.get("client_id", "")
    redirect_uri = params.get("redirect_uri", "")
    state = params.get("state", "")
    scope = params.get("scope", "paprika")
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "S256")

    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)
    if code_challenge_method != "S256":
        return JSONResponse(
            {
                "error": "invalid_request",
                "error_description": "Only S256 PKCE is supported",
            },
            status_code=400,
        )
    if not code_challenge:
        return JSONResponse(
            {
                "error": "invalid_request",
                "error_description": "code_challenge is required",
            },
            status_code=400,
        )

    client = await anyio.to_thread.run_sync(store.get_client, client_id)
    if not client:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    if not secrets.compare_digest(client["redirect_uri"], redirect_uri):
        return JSONResponse(
            {"error": "invalid_request", "error_description": "redirect_uri mismatch"},
            status_code=400,
        )

    if request.method == "GET":
        page = _authorize_page(
            client_name=client["client_name"],
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        return HTMLResponse(page)

    # POST: verify the passphrase.
    if _rate_limited(client_id):
        page = _authorize_page(
            client_name=client["client_name"],
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            error="Too many attempts. Wait a few minutes and try again.",
        )
        return HTMLResponse(page, status_code=429)

    passphrase = params.get("passphrase", "")
    if not secrets.compare_digest(passphrase, config.passphrase):
        _record_failure(client_id)
        page = _authorize_page(
            client_name=client["client_name"],
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            error="Incorrect passphrase.",
        )
        return HTMLResponse(page, status_code=401)

    code = secrets.token_urlsafe(32)
    await anyio.to_thread.run_sync(
        store.store_auth_code,
        code,
        client_id,
        redirect_uri,
        code_challenge,
        scope,
        config.auth_code_ttl,
    )

    separator = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{separator}code={code}"
    if state:
        location += f"&state={state}"
    return RedirectResponse(location, status_code=302)


# --------------------------------------------------------------------------
# /token
# --------------------------------------------------------------------------


async def token(request: Request) -> Response:
    config: Config = request.app.state.config
    store: Store = request.app.state.store

    form = await request.form()
    grant_type = form.get("grant_type")

    creds = _basic_auth_credentials(request)
    if creds:
        client_id, client_secret = creds
    else:
        client_id = form.get("client_id", "")
        client_secret = form.get("client_secret", "")

    if not await anyio.to_thread.run_sync(
        store.verify_client, client_id, client_secret
    ):
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    if grant_type == "authorization_code":
        code = form.get("code", "")
        redirect_uri = form.get("redirect_uri", "")
        code_verifier = form.get("code_verifier", "")

        row = await anyio.to_thread.run_sync(store.consume_auth_code, code, client_id)
        if not row:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if not secrets.compare_digest(row["redirect_uri"], redirect_uri):
            return JSONResponse(
                {
                    "error": "invalid_grant",
                    "error_description": "redirect_uri mismatch",
                },
                status_code=400,
            )
        if not code_verifier or not _verify_pkce(code_verifier, row["code_challenge"]):
            return JSONResponse(
                {
                    "error": "invalid_grant",
                    "error_description": "PKCE verification failed",
                },
                status_code=400,
            )

        scope = row["scope"]
        access_token = _issue_access_token(config, client_id, scope)
        refresh_token = secrets.token_urlsafe(32)
        await anyio.to_thread.run_sync(
            store.store_refresh_token,
            refresh_token,
            client_id,
            scope,
            config.refresh_token_ttl,
        )
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": config.access_token_ttl,
                "refresh_token": refresh_token,
                "scope": scope,
            }
        )

    if grant_type == "refresh_token":
        refresh_token_value = form.get("refresh_token", "")
        row = await anyio.to_thread.run_sync(
            store.consume_refresh_token, refresh_token_value, client_id
        )
        if not row:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        scope = row["scope"]
        access_token = _issue_access_token(config, client_id, scope)
        new_refresh_token = secrets.token_urlsafe(32)
        await anyio.to_thread.run_sync(
            store.store_refresh_token,
            new_refresh_token,
            client_id,
            scope,
            config.refresh_token_ttl,
        )
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": config.access_token_ttl,
                "refresh_token": new_refresh_token,
                "scope": scope,
            }
        )

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
