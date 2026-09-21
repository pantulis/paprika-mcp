"""SQLite-backed storage for the minimal OAuth authorization server.

This is single-user, single-client by design: there's one owner (you) and
normally one registered client (Gemini). This store holds only OAuth
protocol state -- registered clients, authorization codes, refresh tokens --
never Paprika data, which is never cached here.

All methods are synchronous; call them from async route handlers via
`anyio.to_thread.run_sync` so a slow disk doesn't block the event loop.
Secrets and tokens are stored only as SHA-256 hashes, never in plaintext.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    client_secret_hash TEXT NOT NULL,
    client_name TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_codes (
    code_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    scope TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    revoked INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
"""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- Clients --------------------------------------------------------

    def create_client(
        self, client_id: str, client_secret: str, client_name: str, redirect_uri: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO clients "
                "(client_id, client_secret_hash, client_name, redirect_uri, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    client_id,
                    _hash(client_secret),
                    client_name,
                    redirect_uri,
                    int(time.time()),
                ),
            )

    def get_client(self, client_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()

    def verify_client(self, client_id: str, client_secret: str) -> bool:
        client = self.get_client(client_id)
        if not client:
            return False
        return secrets.compare_digest(
            client["client_secret_hash"], _hash(client_secret)
        )

    # -- Authorization codes ---------------------------------------------

    def store_auth_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        scope: str,
        ttl_seconds: int = 60,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_codes "
                "(code_hash, client_id, redirect_uri, code_challenge, scope, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _hash(code),
                    client_id,
                    redirect_uri,
                    code_challenge,
                    scope,
                    int(time.time()) + ttl_seconds,
                ),
            )

    def consume_auth_code(self, code: str, client_id: str) -> sqlite3.Row | None:
        """Fetch and mark used in one call. Returns None if missing/expired/used."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM auth_codes WHERE code_hash = ? AND client_id = ?",
                (_hash(code), client_id),
            ).fetchone()
            if not row:
                return None
            if row["used"] or row["expires_at"] < int(time.time()):
                return None
            conn.execute(
                "UPDATE auth_codes SET used = 1 WHERE code_hash = ?",
                (row["code_hash"],),
            )
            return row

    # -- Refresh tokens ---------------------------------------------------

    def store_refresh_token(
        self, token: str, client_id: str, scope: str, ttl_seconds: int
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO refresh_tokens "
                "(token_hash, client_id, scope, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    _hash(token),
                    client_id,
                    scope,
                    int(time.time()) + ttl_seconds,
                    int(time.time()),
                ),
            )

    def consume_refresh_token(self, token: str, client_id: str) -> sqlite3.Row | None:
        """Validate and consume a refresh token (the caller then rotates it).

        If the token was already used or revoked, this is treated as
        possible token theft: every refresh token for the client is revoked
        and None is returned, forcing a fresh /authorize login.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM refresh_tokens WHERE token_hash = ? AND client_id = ?",
                (_hash(token), client_id),
            ).fetchone()
            if not row:
                return None
            if row["used"] or row["revoked"] or row["expires_at"] < int(time.time()):
                conn.execute(
                    "UPDATE refresh_tokens SET revoked = 1 WHERE client_id = ?",
                    (client_id,),
                )
                return None
            conn.execute(
                "UPDATE refresh_tokens SET used = 1 WHERE token_hash = ?",
                (row["token_hash"],),
            )
            return row
