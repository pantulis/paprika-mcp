"""Unit tests for the Redis-backed OAuth store."""

import asyncio

from paprika_mcp.http.store import Store


async def test_create_and_verify_client(store: Store):
    await store.create_client(
        "client-1", "secret-1", "Test Client", "https://example.com/cb"
    )
    assert await store.verify_client("client-1", "secret-1") is True
    assert await store.verify_client("client-1", "wrong-secret") is False
    assert await store.verify_client("unknown-client", "secret-1") is False


async def test_get_client(store: Store):
    await store.create_client(
        "client-1", "secret-1", "Test Client", "https://example.com/cb"
    )
    client = await store.get_client("client-1")
    assert client is not None
    assert client["client_name"] == "Test Client"
    assert client["redirect_uri"] == "https://example.com/cb"
    assert await store.get_client("missing") is None


async def test_auth_code_roundtrip(store: Store):
    await store.store_auth_code(
        "code-1",
        "client-1",
        "https://example.com/cb",
        "challenge-1",
        "paprika",
        ttl_seconds=60,
    )
    row = await store.consume_auth_code("code-1", "client-1")
    assert row is not None
    assert row["redirect_uri"] == "https://example.com/cb"
    assert row["code_challenge"] == "challenge-1"

    # Cannot be consumed twice.
    assert await store.consume_auth_code("code-1", "client-1") is None


async def test_auth_code_expired(store: Store):
    # Redis' SET...EX requires a positive TTL (unlike the old SQLite version's
    # manual expires_at comparison, a negative value is simply rejected), so
    # exercise real expiry with the smallest valid TTL plus a short wait.
    await store.store_auth_code(
        "code-1",
        "client-1",
        "https://example.com/cb",
        "challenge-1",
        "paprika",
        ttl_seconds=1,
    )
    await asyncio.sleep(1.2)
    assert await store.consume_auth_code("code-1", "client-1") is None


async def test_auth_code_wrong_client_rejected(store: Store):
    await store.store_auth_code(
        "code-1",
        "client-1",
        "https://example.com/cb",
        "challenge-1",
        "paprika",
        ttl_seconds=60,
    )
    assert await store.consume_auth_code("code-1", "other-client") is None


async def test_refresh_token_roundtrip(store: Store):
    await store.store_refresh_token(
        "refresh-1", "client-1", "paprika", ttl_seconds=3600
    )
    row = await store.consume_refresh_token("refresh-1", "client-1")
    assert row is not None
    assert row["scope"] == "paprika"


async def test_refresh_token_reuse_revokes_all(store: Store):
    """Reusing a consumed refresh token is treated as possible theft: every
    refresh token for that client is revoked, not just the reused one."""
    await store.store_refresh_token(
        "refresh-1", "client-1", "paprika", ttl_seconds=3600
    )
    await store.store_refresh_token(
        "refresh-2", "client-1", "paprika", ttl_seconds=3600
    )

    assert await store.consume_refresh_token("refresh-1", "client-1") is not None
    assert await store.consume_refresh_token("refresh-1", "client-1") is None
    assert await store.consume_refresh_token("refresh-2", "client-1") is None


async def test_refresh_token_wrong_client_rejected(store: Store):
    await store.store_refresh_token(
        "refresh-1", "client-1", "paprika", ttl_seconds=3600
    )
    assert await store.consume_refresh_token("refresh-1", "other-client") is None


async def test_refresh_token_missing_is_not_treated_as_reuse(store: Store):
    """A token that never existed shouldn't trigger theft-detection --
    only a *confirmed* reuse of a token we actually issued should."""
    assert await store.consume_refresh_token("never-issued", "client-1") is None
    # Prove no epoch bump happened: a legitimately issued token still works.
    await store.store_refresh_token(
        "refresh-1", "client-1", "paprika", ttl_seconds=3600
    )
    assert await store.consume_refresh_token("refresh-1", "client-1") is not None


async def test_refresh_token_expired(store: Store):
    await store.store_refresh_token("refresh-1", "client-1", "paprika", ttl_seconds=1)
    await asyncio.sleep(1.2)
    assert await store.consume_refresh_token("refresh-1", "client-1") is None
