"""Runtime configuration for the HTTP/OAuth transport, loaded from env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_url: str  # e.g. "https://paprika-mcp.onrender.com" -- no trailing slash
    passphrase: str
    jwt_secret: str
    redis_url: str  # e.g. Render Key Value's internal redis:// connection string
    access_token_ttl: int = 3600
    refresh_token_ttl: int = 60 * 60 * 24 * 90  # 90 days
    auth_code_ttl: int = 60

    @property
    def resource_url(self) -> str:
        """The canonical URL of the protected MCP endpoint (the JWT audience)."""
        return f"{self.base_url}/mcp"

    @classmethod
    def from_env(cls) -> Config:
        base_url = os.environ.get("PUBLIC_BASE_URL")
        passphrase = os.environ.get("MCP_PASSPHRASE")
        jwt_secret = os.environ.get("JWT_SECRET")
        redis_url = os.environ.get("REDIS_URL")

        missing = [
            name
            for name, value in (
                ("PUBLIC_BASE_URL", base_url),
                ("MCP_PASSPHRASE", passphrase),
                ("JWT_SECRET", jwt_secret),
                ("REDIS_URL", redis_url),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "PUBLIC_BASE_URL is the server's own public URL, e.g. "
                "https://paprika-mcp.onrender.com (no trailing slash). REDIS_URL "
                "points at a Redis-protocol server (Render Key Value in "
                "production, or e.g. redis://localhost:6379 for local dev -- "
                "see README's 'Remote Access' section)."
            )

        return cls(
            base_url=base_url.rstrip("/"),  # type: ignore[union-attr]
            passphrase=passphrase,  # type: ignore[arg-type]
            jwt_secret=jwt_secret,  # type: ignore[arg-type]
            redis_url=redis_url,  # type: ignore[arg-type]
        )
