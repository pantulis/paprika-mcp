"""CLI utilities for paprika-mcp."""

import asyncio
import json
import os
import secrets
import sys
from getpass import getpass


def setup_credentials():
    """Interactive credential setup."""
    config_dir = os.path.expanduser("~/.paprika-mcp")
    config_file = os.path.join(config_dir, "config.json")

    print("Paprika MCP Server - Credential Setup")
    print("=" * 50)

    # Check if config already exists
    if os.path.exists(config_file):
        print(f"\nConfig file already exists: {config_file}")
        response = input("Overwrite existing credentials? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Cancelled.")
            return

    # Get credentials
    print("\nEnter your Paprika account credentials:")
    email = input("Email: ").strip()
    if not email:
        print("Error: Email is required")
        sys.exit(1)

    password = getpass("Password: ")
    if not password:
        print("Error: Password is required")
        sys.exit(1)

    # Create config directory if needed
    os.makedirs(config_dir, exist_ok=True)

    # Write config
    config = {"email": email, "password": password}
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    # Set permissions
    os.chmod(config_file, 0o600)

    print(f"\n✓ Credentials saved to: {config_file}")
    print("  File permissions: 600 (user read/write only)")
    print("\nYou can now start the MCP server with: paprika-mcp")


def serve():
    """Run the remote (Streamable HTTP + OAuth) server, for clients like Gemini.

    Reads PUBLIC_BASE_URL, MCP_PASSPHRASE, JWT_SECRET, REDIS_URL (required)
    and PORT (optional) from the environment. Local stdio clients (e.g.
    Claude Code) should keep using the default `paprika-mcp` entrypoint
    instead -- this is only for remote access.
    """
    import uvicorn

    from paprika_mcp.http.app import create_app

    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


def register_client():
    """Register an OAuth client (e.g. Gemini) for the HTTP transport.

    Usage: paprika-mcp register-client --redirect-uri <uri> [--name <name>]

    Run this once per client, against the same environment (REDIS_URL etc)
    the `serve` command uses -- in production, over Render's shell for the
    web service, so it reaches the same internal Key Value instance. Prints
    the Client ID and Secret exactly once -- copy them into the client's
    OAuth setup form immediately.
    """
    from paprika_mcp.http.config import Config
    from paprika_mcp.http.store import Store

    args = sys.argv[2:]
    redirect_uri = None
    client_name = "Gemini"
    i = 0
    while i < len(args):
        if args[i] == "--redirect-uri" and i + 1 < len(args):
            redirect_uri = args[i + 1]
            i += 2
        elif args[i] == "--name" and i + 1 < len(args):
            client_name = args[i + 1]
            i += 2
        else:
            i += 1

    if not redirect_uri:
        print("Usage: paprika-mcp register-client --redirect-uri <uri> [--name <name>]")
        sys.exit(1)

    async def _register() -> tuple[str, str]:
        config = Config.from_env()
        store = Store.from_url(config.redis_url)
        try:
            client_id = secrets.token_urlsafe(16)
            client_secret = secrets.token_urlsafe(32)
            await store.create_client(
                client_id, client_secret, client_name, redirect_uri
            )
            return client_id, client_secret
        finally:
            await store.aclose()

    client_id, client_secret = asyncio.run(_register())

    print("Client registered.")
    print(f"  Client ID:     {client_id}")
    print(f"  Client Secret: {client_secret}")
    print(f"  Redirect URI:  {redirect_uri}")
    print()
    print("This secret is shown only once. Paste the Client ID and Secret into")
    print("the client's 'Advanced features' OAuth credentials form now.")


def main():
    """Main CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_credentials()
    elif len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve()
    elif len(sys.argv) > 1 and sys.argv[1] == "register-client":
        register_client()
    else:
        # Start the server (stdio, for local MCP clients)
        from paprika_mcp.server import run

        run()


if __name__ == "__main__":
    main()
