"""Tests for the secret-gated POST /admin/register-client endpoint."""

from __future__ import annotations

from .conftest import TEST_ADMIN_SECRET


async def test_register_client_requires_secret(client):
    resp = await client.post(
        "/admin/register-client",
        json={
            "redirect_uri": "https://new-client.example.com/cb",
            "name": "New Client",
        },
    )
    assert resp.status_code == 401


async def test_register_client_rejects_wrong_secret(client):
    resp = await client.post(
        "/admin/register-client",
        headers={"X-Admin-Secret": "not-the-real-secret"},
        json={"redirect_uri": "https://new-client.example.com/cb"},
    )
    assert resp.status_code == 401


async def test_register_client_succeeds_with_correct_secret(client):
    resp = await client.post(
        "/admin/register-client",
        headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        json={
            "redirect_uri": "https://new-client.example.com/cb",
            "name": "New Client",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["client_name"] == "New Client"
    assert body["redirect_uri"] == "https://new-client.example.com/cb"
    assert body["client_id"]
    assert body["client_secret"]


async def test_register_client_requires_redirect_uri(client):
    resp = await client.post(
        "/admin/register-client",
        headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        json={"name": "Missing redirect_uri"},
    )
    assert resp.status_code == 400


async def test_registered_client_is_actually_usable(client):
    """The point of the endpoint: a client it creates can immediately
    authenticate to /token like any other registered client."""
    resp = await client.post(
        "/admin/register-client",
        headers={"X-Admin-Secret": TEST_ADMIN_SECRET},
        json={
            "redirect_uri": "https://new-client.example.com/cb",
            "name": "New Client",
        },
    )
    created = resp.json()

    resp = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": created["client_id"],
            "redirect_uri": created["redirect_uri"],
            "code_challenge": "irrelevant-for-this-check",
            "code_challenge_method": "S256",
        },
    )
    # Reaching the passphrase form (not invalid_client) proves the store
    # actually persisted the client this endpoint just created.
    assert resp.status_code == 200
    assert "passphrase" in resp.text


async def test_admin_endpoint_disabled_when_no_admin_secret(app_and_store_factory):
    """Without ADMIN_SECRET configured, the endpoint doesn't exist at all
    (404) rather than existing unguarded."""
    app, _ = await app_and_store_factory(admin_secret=None)

    import httpx
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
            resp = await c.post(
                "/admin/register-client",
                headers={"X-Admin-Secret": "anything"},
                json={"redirect_uri": "https://x.example.com/cb"},
            )
            assert resp.status_code == 404
