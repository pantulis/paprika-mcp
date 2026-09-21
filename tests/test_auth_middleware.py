"""Tests for BearerAuthMiddleware's protection of /mcp."""

from __future__ import annotations

import time

import jwt


async def test_mcp_requires_bearer_token(client):
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert "oauth-protected-resource" in resp.headers["WWW-Authenticate"]


async def test_mcp_rejects_garbage_token(client):
    resp = await client.post(
        "/mcp",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


async def test_mcp_rejects_expired_token(client):
    payload = {
        "iss": "http://testserver",
        "aud": "http://testserver/mcp",
        "sub": "owner",
        "client_id": "client-1",
        "scope": "paprika",
        "iat": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600,
    }
    expired = jwt.encode(
        payload, "test-jwt-secret-that-is-long-enough-for-hs256", algorithm="HS256"
    )
    resp = await client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {expired}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


async def test_mcp_rejects_wrong_audience(client):
    payload = {
        "iss": "http://testserver",
        "aud": "http://some-other-server/mcp",
        "sub": "owner",
        "client_id": "client-1",
        "scope": "paprika",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(
        payload, "test-jwt-secret-that-is-long-enough-for-hs256", algorithm="HS256"
    )
    resp = await client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert resp.status_code == 401


async def test_non_mcp_routes_are_not_gated(client):
    # /healthz and the .well-known docs must stay reachable with no token.
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    resp = await client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
