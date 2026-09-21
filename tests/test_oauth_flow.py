"""End-to-end test of the OAuth 2.1 authorization flow against the real
Starlette app, driven in-process over httpx's ASGI transport (no sockets,
no real Paprika account).
"""

from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlparse

from .conftest import TEST_PASSPHRASE, TEST_REDIRECT_URI, make_pkce_pair

BASIC_AUTH = base64.b64encode(b"client-1:secret-1").decode("ascii")


async def _authorize_and_get_code(client, code_challenge, state="xyz"):
    resp = await client.post(
        "/authorize",
        data={
            "client_id": "client-1",
            "redirect_uri": TEST_REDIRECT_URI,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "paprika",
            "passphrase": TEST_PASSPHRASE,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    return parse_qs(urlparse(resp.headers["location"]).query)["code"][0]


async def test_metadata_documents(client):
    resp = await client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["issuer"] == "http://testserver"
    # DCR is intentionally not offered -- see http/oauth.py module docstring.
    assert "registration_endpoint" not in meta
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["token_endpoint_auth_methods_supported"] == ["client_secret_basic"]

    resp = await client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"] == "http://testserver/mcp"
    assert body["authorization_servers"] == ["http://testserver"]


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_authorize_rejects_unknown_client(client):
    _, challenge = make_pkce_pair()
    resp = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": "no-such-client",
            "redirect_uri": TEST_REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client"


async def test_authorize_rejects_redirect_uri_mismatch(client):
    _, challenge = make_pkce_pair()
    resp = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": "client-1",
            "redirect_uri": "https://evil.example.com/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


async def test_authorize_wrong_passphrase_rejected(client):
    _, challenge = make_pkce_pair()
    resp = await client.post(
        "/authorize",
        data={
            "client_id": "client-1",
            "redirect_uri": TEST_REDIRECT_URI,
            "state": "xyz",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "paprika",
            "passphrase": "wrong",
        },
    )
    assert resp.status_code == 401


async def test_full_authorization_code_and_refresh_flow(client):
    verifier, challenge = make_pkce_pair()
    code = await _authorize_and_get_code(client, challenge)

    # Exchange the code for tokens, authenticating as the client.
    resp = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={"Authorization": f"Basic {BASIC_AUTH}"},
    )
    assert resp.status_code == 200
    tokens = resp.json()
    assert tokens["token_type"] == "Bearer"
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # The code cannot be reused.
    resp = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={"Authorization": f"Basic {BASIC_AUTH}"},
    )
    assert resp.status_code == 400

    # The access token authorizes an MCP initialize call. Starlette's Mount
    # 307-redirects a bare "/mcp" to "/mcp/" (matching the upstream MCP SDK's
    # own example server); real HTTP clients, including Gemini's, follow a
    # 307 on POST transparently since it preserves method and body.
    resp = await client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {access_token}",
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        },
        follow_redirects=True,
        content=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        ),
    )
    assert resp.status_code == 200

    # Refresh rotation: the old refresh token can't be reused after rotating.
    resp = await client.post(
        "/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Authorization": f"Basic {BASIC_AUTH}"},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["access_token"] != access_token
    assert new_tokens["refresh_token"] != refresh_token

    resp = await client.post(
        "/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Authorization": f"Basic {BASIC_AUTH}"},
    )
    assert resp.status_code == 400


async def test_wrong_pkce_verifier_rejected(client):
    wrong_verifier, _ = make_pkce_pair()
    _, challenge = make_pkce_pair()
    code = await _authorize_and_get_code(client, challenge)

    resp = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "code_verifier": wrong_verifier,
        },
        headers={"Authorization": f"Basic {BASIC_AUTH}"},
    )
    assert resp.status_code == 400


async def test_token_rejects_unknown_client_credentials(client):
    verifier, challenge = make_pkce_pair()
    code = await _authorize_and_get_code(client, challenge)

    bad_basic = base64.b64encode(b"client-1:wrong-secret").decode("ascii")
    resp = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={"Authorization": f"Basic {bad_basic}"},
    )
    assert resp.status_code == 401
