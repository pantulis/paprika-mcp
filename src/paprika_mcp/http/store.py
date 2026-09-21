"""Redis-backed storage for the minimal OAuth authorization server.

This is single-user, single-client by design: there's one owner (you) and
normally one registered client (Gemini). This store holds only OAuth
protocol state -- registered clients, authorization codes, refresh tokens --
never Paprika data, which is never cached here.

Backed by Render's free Key Value instance (a real Redis-protocol service),
reached via `redis.asyncio`. Free-tier Key Value has no durability
guarantee -- see the project plan/README for why that tradeoff was accepted
for this single-user server. Secrets and tokens are stored only as SHA-256
hashes, never in plaintext.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any, TypedDict, cast

from redis.asyncio import Redis


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ClientRow(TypedDict):
    client_id: str
    client_secret_hash: str
    client_name: str
    redirect_uri: str


class AuthCodeRow(TypedDict):
    client_id: str
    redirect_uri: str
    code_challenge: str
    scope: str


class RefreshTokenRow(TypedDict):
    client_id: str
    scope: str


class Store:
    def __init__(self, redis: Redis):
        self._redis = redis

    @classmethod
    def from_url(cls, redis_url: str) -> Store:
        return cls(Redis.from_url(redis_url, decode_responses=True))

    async def aclose(self) -> None:
        await self._redis.aclose()

    # -- Clients --------------------------------------------------------

    async def create_client(
        self, client_id: str, client_secret: str, client_name: str, redirect_uri: str
    ) -> None:
        await self._redis.hset(
            f"client:{client_id}",
            mapping={
                "client_secret_hash": _hash(client_secret),
                "client_name": client_name,
                "redirect_uri": redirect_uri,
                "created_at": int(time.time()),
            },
        )

    async def get_client(self, client_id: str) -> ClientRow | None:
        # decode_responses=True means these come back as str, not bytes;
        # redis-py's stubs aren't precise enough to reflect that.
        data = cast("dict[str, str]", await self._redis.hgetall(f"client:{client_id}"))
        if not data:
            return None
        return {
            "client_id": client_id,
            "client_secret_hash": data["client_secret_hash"],
            "client_name": data["client_name"],
            "redirect_uri": data["redirect_uri"],
        }

    async def verify_client(self, client_id: str, client_secret: str) -> bool:
        client = await self.get_client(client_id)
        if not client:
            return False
        return secrets.compare_digest(
            client["client_secret_hash"], _hash(client_secret)
        )

    # -- Authorization codes ---------------------------------------------

    async def store_auth_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        scope: str,
        ttl_seconds: int = 60,
    ) -> None:
        payload: AuthCodeRow = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "scope": scope,
        }
        await self._redis.set(
            f"authcode:{_hash(code)}", json.dumps(payload), ex=ttl_seconds
        )

    async def consume_auth_code(self, code: str, client_id: str) -> AuthCodeRow | None:
        """Atomically fetch-and-delete. Returns None if missing/expired/
        already used, or if it belongs to a different client.

        A single-use code is safe to delete outright on consumption (unlike
        a refresh token, nothing downstream needs to tell "reused" apart
        from "never existed" for a code -- both are just a failed exchange).
        """
        raw = await self._redis.getdel(f"authcode:{_hash(code)}")
        if raw is None:
            return None
        row: AuthCodeRow = json.loads(raw)
        if row["client_id"] != client_id:
            return None
        return row

    # -- Refresh tokens ---------------------------------------------------

    async def _client_epoch(self, client_id: str) -> int:
        value = await self._redis.get(f"client_epoch:{client_id}")
        return int(value) if value is not None else 0

    async def store_refresh_token(
        self, token: str, client_id: str, scope: str, ttl_seconds: int
    ) -> None:
        epoch = await self._client_epoch(client_id)
        payload: dict[str, Any] = {
            "client_id": client_id,
            "scope": scope,
            "epoch": epoch,
        }
        await self._redis.set(
            f"refreshtoken:{_hash(token)}", json.dumps(payload), ex=ttl_seconds
        )

    async def consume_refresh_token(
        self, token: str, client_id: str
    ) -> RefreshTokenRow | None:
        """Validate and consume a refresh token (the caller then rotates it).

        Uses two keys per token: the payload (read-only after creation, so
        it's never destroyed by consuming it) and a separate `:used` marker
        claimed with `SET NX` -- atomic, so of two concurrent consume calls
        for the same token at most one can win. A token that's simply
        missing (expired, unknown) is rejected with no side effect: that's
        not evidence of anything. Losing the NX race (the marker already
        exists) means someone already consumed this exact token, which *is*
        evidence of reuse and is treated as possible theft -- the client's
        epoch is bumped, invalidating every other refresh token minted
        before now, forcing a fresh /authorize login.
        """
        key = f"refreshtoken:{_hash(token)}"
        raw = await self._redis.get(key)
        if raw is None:
            return None

        row: dict[str, Any] = json.loads(raw)
        if row["client_id"] != client_id:
            return None

        ttl = await self._redis.ttl(key)
        claimed = await self._redis.set(f"{key}:used", "1", nx=True, ex=max(ttl, 1))
        if not claimed:
            await self._redis.incr(f"client_epoch:{client_id}")
            return None

        current_epoch = await self._client_epoch(client_id)
        if row["epoch"] != current_epoch:
            # Minted under an epoch that's since been revoked.
            return None

        return {"client_id": row["client_id"], "scope": row["scope"]}
