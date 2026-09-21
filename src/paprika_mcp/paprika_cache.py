"""A Redis-backed cache for `paprika_recipes.Remote`'s recipe cache.

`paprika_recipes.cache.Cache` is a small synchronous interface `Remote`
calls internally (`is_cached`, `store_in_cache`, `read_from_cache`, `save`)
-- built exactly for pluggable backends, the same one `DirectoryCache` (the
upstream default, local-disk) implements.

This exists because Render's free web-service disk is ephemeral: without a
persistent cache, every cold start would look like a first-ever sync and
re-fetch every recipe individually in one tight burst (the Paprika v2 API's
list endpoint only returns `{uid, hash}` pairs -- full recipe data is one
API call per recipe). That risks tripping whatever undocumented rate
limiting the unofficial API has. A cache that survives restarts turns a
cold start back into "fetch only what actually changed," same as a warm
disk cache would.

Uses the plain synchronous `redis` client, not `redis.asyncio`: `Cache`'s
methods are synchronous and get called from `Remote`'s synchronous code
paths, which our MCP tool handlers invoke from inside an already-running
asyncio event loop (uvicorn's). Reaching for the async client here would
mean bridging into that loop from sync code, which is real complexity for
no real benefit -- these are small, fast calls over Render's internal
network, so blocking briefly is a non-issue for a personal, low-traffic
server.
"""

from __future__ import annotations

import json
from typing import Any

from paprika_recipes.cache import Cache, NotFound
from redis import Redis

_KEY_PREFIX = "recipe:"


class RedisCache(Cache):
    def __init__(self, redis_url: str):
        self._redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    def is_cached(self, uid: str, hash: str) -> bool:
        stored_hash = self._redis.hget(f"{_KEY_PREFIX}{uid}", "hash")
        return stored_hash == hash

    def store_in_cache(self, uid: str, hash: str, recipe: dict[str, Any]) -> None:
        self._redis.hset(
            f"{_KEY_PREFIX}{uid}",
            mapping={"hash": hash, "data": json.dumps(recipe)},
        )

    def read_from_cache(self, uid: str, hash: str) -> dict[str, Any]:
        if not self.is_cached(uid, hash):
            raise NotFound()
        raw = self._redis.hget(f"{_KEY_PREFIX}{uid}", "data")
        if raw is None:
            return {}
        data: dict[str, Any] = json.loads(raw)
        return data

    def save(self) -> None:
        # No-op: every write above is already persisted immediately.
        pass
