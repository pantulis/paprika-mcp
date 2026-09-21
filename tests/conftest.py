"""Shared pytest fixtures for the HTTP/OAuth test suite."""

from __future__ import annotations

import base64
import hashlib
import secrets

import httpx
import pytest
from asgi_lifespan import LifespanManager

from paprika_mcp.http.store import Store

TEST_PASSPHRASE = "correct-horse-battery-staple"
TEST_REDIRECT_URI = "https://client.example.com/callback"


def make_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for an S256 PKCE exchange."""
    verifier = secrets.token_urlsafe(64)[:64]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(str(tmp_path / "oauth.db"))


@pytest.fixture
def app_and_store(monkeypatch, tmp_path):
    """Build the real Starlette app against a temp SQLite DB, with one
    pre-registered test client (mirroring `register-client`)."""
    db_path = str(tmp_path / "oauth.db")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    monkeypatch.setenv("MCP_PASSPHRASE", TEST_PASSPHRASE)
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-that-is-long-enough-for-hs256")
    monkeypatch.setenv("PAPRIKA_MCP_DB", db_path)

    from paprika_mcp.http.app import create_app

    app = create_app()
    test_store = Store(db_path)
    test_store.create_client("client-1", "secret-1", "Test Client", TEST_REDIRECT_URI)
    return app, test_store


@pytest.fixture
async def client(app_and_store):
    """An httpx client wired to the real app, with ASGI lifespan (startup/
    shutdown) actually driven -- httpx.ASGITransport doesn't do this on its
    own, but the app relies on lifespan to start the MCP session manager's
    task group (see http/app.py's `lifespan`)."""
    app, _ = app_and_store
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
            yield c
