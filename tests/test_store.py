"""Unit tests for the OAuth SQLite store."""

from paprika_mcp.http.store import Store


def test_create_and_verify_client(store: Store):
    store.create_client("client-1", "secret-1", "Test Client", "https://example.com/cb")
    assert store.verify_client("client-1", "secret-1") is True
    assert store.verify_client("client-1", "wrong-secret") is False
    assert store.verify_client("unknown-client", "secret-1") is False


def test_get_client(store: Store):
    store.create_client("client-1", "secret-1", "Test Client", "https://example.com/cb")
    client = store.get_client("client-1")
    assert client is not None
    assert client["client_name"] == "Test Client"
    assert client["redirect_uri"] == "https://example.com/cb"
    assert store.get_client("missing") is None


def test_auth_code_roundtrip(store: Store):
    store.store_auth_code(
        "code-1",
        "client-1",
        "https://example.com/cb",
        "challenge-1",
        "paprika",
        ttl_seconds=60,
    )
    row = store.consume_auth_code("code-1", "client-1")
    assert row is not None
    assert row["redirect_uri"] == "https://example.com/cb"
    assert row["code_challenge"] == "challenge-1"

    # Cannot be consumed twice.
    assert store.consume_auth_code("code-1", "client-1") is None


def test_auth_code_expired(store: Store):
    store.store_auth_code(
        "code-1",
        "client-1",
        "https://example.com/cb",
        "challenge-1",
        "paprika",
        ttl_seconds=-1,
    )
    assert store.consume_auth_code("code-1", "client-1") is None


def test_auth_code_wrong_client_rejected(store: Store):
    store.store_auth_code(
        "code-1",
        "client-1",
        "https://example.com/cb",
        "challenge-1",
        "paprika",
        ttl_seconds=60,
    )
    assert store.consume_auth_code("code-1", "other-client") is None


def test_refresh_token_roundtrip(store: Store):
    store.store_refresh_token("refresh-1", "client-1", "paprika", ttl_seconds=3600)
    row = store.consume_refresh_token("refresh-1", "client-1")
    assert row is not None
    assert row["scope"] == "paprika"


def test_refresh_token_reuse_revokes_all(store: Store):
    """Reusing a consumed refresh token is treated as possible theft: every
    refresh token for that client is revoked, not just the reused one."""
    store.store_refresh_token("refresh-1", "client-1", "paprika", ttl_seconds=3600)
    store.store_refresh_token("refresh-2", "client-1", "paprika", ttl_seconds=3600)

    assert store.consume_refresh_token("refresh-1", "client-1") is not None
    assert store.consume_refresh_token("refresh-1", "client-1") is None
    assert store.consume_refresh_token("refresh-2", "client-1") is None


def test_refresh_token_expired(store: Store):
    store.store_refresh_token("refresh-1", "client-1", "paprika", ttl_seconds=-1)
    assert store.consume_refresh_token("refresh-1", "client-1") is None
