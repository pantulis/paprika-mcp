"""Runtime configuration for the HTTP/OAuth transport, loaded from env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_url: str  # e.g. "https://paprika-mcp.fly.dev" -- no trailing slash
    passphrase: str
    jwt_secret: str
    db_path: str
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

        missing = [
            name
            for name, value in (
                ("PUBLIC_BASE_URL", base_url),
                ("MCP_PASSPHRASE", passphrase),
                ("JWT_SECRET", jwt_secret),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "PUBLIC_BASE_URL is the server's own public URL, e.g. "
                "https://paprika-mcp.fly.dev (no trailing slash)."
            )

        default_db = os.path.expanduser("~/.paprika-mcp/oauth.db")
        return cls(
            base_url=base_url.rstrip("/"),  # type: ignore[union-attr]
            passphrase=passphrase,  # type: ignore[arg-type]
            jwt_secret=jwt_secret,  # type: ignore[arg-type]
            db_path=os.environ.get("PAPRIKA_MCP_DB", default_db),
        )
