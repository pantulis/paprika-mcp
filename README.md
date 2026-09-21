# Paprika MCP Server

A Model Context Protocol (MCP) server for the Paprika Recipe Manager, allowing AI assistants to search, read, and update recipes, manage grocery lists, and plan meals.

This is a fork of [briantkatch/paprika-mcp](https://github.com/briantkatch/paprika-mcp) that adds grocery list, meal plan, and recipe create/trash tools, plus a remote (Streamable HTTP + OAuth 2.1) transport so the server can be hosted in the cloud and connected to clients like **Gemini's custom-app connector**, not just run locally over stdio.

## Features

- **Recipes**: search, read, create, update (find/replace), and trash (soft delete)
- **Groceries**: list, add items, add a recipe's ingredients in one step, and check items off
- **Meal plan**: list entries by date range, plan a meal (linked to a recipe or text-only)
- **Pantry**: list inventory (read-only -- see [Pantry is read-only](#pantry-is-read-only))
- **Categories**: list, with hierarchy
- **Two transports**: stdio for local clients (Claude Code, Claude Desktop) with no auth, and Streamable HTTP + OAuth 2.1 for remote clients (Gemini)

## Prerequisites

1. Python 3.10 or higher (Python 3.13 recommended)
2. A Paprika account with recipes
3. Node.js (for pre-commit hooks, optional)

## Quick Start

Run the setup script to install everything and configure credentials:

```bash
cd paprika-mcp
./setup.sh
```

This will:
1. Install paprika-mcp with dependencies
2. Set up pre-commit hooks (if npm available)

## Manual Installation

If you prefer manual setup:

### 1. Install paprika-recipes

```bash
cd ../paprika-recipes
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
deactivate
```

### 2. Install paprika-mcp

```bash
cd ../paprika-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure credentials

**Option 1: Interactive setup**

```bash
source .venv/bin/activate
paprika-mcp setup
```

**Option 2: Manual config file**

Create `~/.paprika-mcp/config.json`:

```json
{
  "email": "your@email.com",
  "password": "yourpassword"
}
```

Set permissions:
```bash
chmod 600 ~/.paprika-mcp/config.json
```

**Option 3: Environment variables**

```bash
export PAPRIKA_EMAIL="your@email.com"
export PAPRIKA_PASSWORD="yourpassword"
```

## Credential Management

The server uses a credential flow designed for MCP stdio transport:

**Priority order:**
1. `PAPRIKA_EMAIL` and `PAPRIKA_PASSWORD` environment variables
2. `~/.paprika-mcp/config.json` file

**Note**: This server manages credentials independently from the paprika-recipes CLI tool's keyring storage. This simplifies the credential flow for MCP stdio transport where the process is spawned by the AI app.

## User-Agent

If you have Paprika for Mac installed, the fork of the `paprika-recipes` Python package should automatically create a suitable User-Agent string. Otherwise, you might have to set the `PAPRIKA_USER_AGENT` environment variable or the "user_agent" property in `config.json`.

## Usage

### As an MCP Server

Add to your MCP client configuration (e.g., Claude Desktop's `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "paprika": {
      "command": "/Users/yourusername/Developer/paprika-mcp/.venv/bin/paprika-mcp"
    }
  }
}
```

Or use environment variables:

```json
{
  "mcpServers": {
    "paprika": {
      "command": "/Users/yourusername/Developer/paprika-mcp/.venv/bin/paprika-mcp",
      "env": {
        "PAPRIKA_EMAIL": "your@email.com",
        "PAPRIKA_PASSWORD": "yourpassword"
      }
    }
  }
}
```

### Available Tools

#### format_fraction

Format a fraction string to unicode fraction characters. **This tool is local-only** and doesn't require Paprika server connectivity - useful for testing.

**Parameters:**
- `fraction` (required): Fraction in the form "numerator/denominator" (e.g., "1/4", " 31 / 200 "), or already formatted unicode

**Features:**
- Handles already-formatted unicode fractions (returns them as-is)
- Strips whitespace from input
- Converts common fractions to dedicated unicode characters
- Composes complex fractions using superscript/subscript digits

**Examples:**
```json
{
  "fraction": "1/4"
}
```
Returns: `¼`

```json
{
  "fraction": " 31 / 200 "
}
```
Returns: `³¹⁄₂₀₀` (whitespace stripped)

```json
{
  "fraction": "¼"
}
```
Returns: `¼` (already formatted, returned as-is)

Common fractions (1/4, 1/2, 3/4, 1/3, 2/3, etc.) use dedicated Unicode characters. Complex fractions are composed using superscript numerator + fraction slash (⁄) + subscript denominator.

#### search_recipes

Search for recipes by text across multiple fields.

**Parameters:**
- `query` (required): Text to search for
- `fields` (optional): Array of fields to search in: `["name", "ingredients", "categories", "directions", "notes"]`
- `context_lines` (optional): Number of context lines around matches (default: 2)

**Example:**
```json
{
  "query": "chicken",
  "fields": ["name", "ingredients"],
  "context_lines": 2
}
```

#### read_recipe

Read full recipe data by ID or title.

**Parameters:**
- `id` or `title` (one required): Recipe UUID or exact recipe name

**Note:** Title matching uses Unicode normalization (NFD), so it works correctly with accented characters regardless of their unicode representation (e.g., "café" will match "café").

**Example:**
```json
{
  "id": "RECIPE-UUID-HERE"
}
```

or

```json
{
  "title": "Chocolate Chip Cookies"
}
```

### User Preferences (Prompts)

You can provide context to the AI about how you want it to work with your recipes by creating a `~/.paprika-mcp/prompt.md` file. This will be automatically loaded as a prompt when the MCP server starts.

**Example prompt file:**
```markdown
# Recipe Management Preferences

- Always preserve source URLs and attribution
- Prefer metric measurements
- I'm cooking for 2 people typically
- I avoid peanuts (allergy)
- Categorize using: Breakfast, Lunch, Dinner, Desserts, Snacks
```

See [`prompt.example.md`](prompt.example.md) for a complete template.

#### update_recipe

Update a recipe field using find/replace.

**⚠️ DANGEROUS**: This tool modifies recipe data. User confirmation is recommended before execution.

**Parameters:**
- `id` (required): Recipe UUID
- `field` (required): Field to update (name, ingredients, directions, notes, etc.)
- `find` (required): Text to find
- `replace` (required): Text to replace with
- `regex` (optional): Treat find pattern as regex (default: false)

**Example:**
```json
{
  "id": "RECIPE-UUID-HERE",
  "field": "ingredients",
  "find": "1 cup sugar",
  "replace": "3/4 cup sugar"
}
```

### New tools (this fork)

All of these follow the same call shape as the tools above (`args` dict in, `list[TextContent]` out) and are registered in [`tools/__init__.py`](src/paprika_mcp/tools/__init__.py). Full parameter docs live in each tool's `TOOL_DEFINITION`.

- `create_recipe` -- create a new recipe. Category names are resolved to UUIDs automatically.
- `trash_recipe` -- soft-delete (`in_trash: true`); Paprika has no permanent delete via the API.
- `list_groceries` / `add_groceries` / `check_off_groceries` -- manage grocery items. Checking an item off is also how you clear it; there's no hard delete.
- `add_recipe_to_grocery_list` -- the "add this recipe's ingredients to my list" flow, one grocery item per ingredient line.
- `list_meals` / `plan_meal` -- read and write the meal plan, by date (`YYYY-MM-DD`) and meal type (breakfast/lunch/dinner/snack).
- `list_pantry` -- read-only pantry inventory.
- `sync_status` -- sync counters; also a simple connectivity/auth check.

#### Pantry is read-only

Paprika's pantry *write* schema isn't documented in any known source (not the community API references, not the local SQLite schema docs). Rather than guess at field names and risk silent no-op writes, this server only reads pantry data.

## Remote Access (Streamable HTTP + OAuth, for Gemini)

Gemini's "Custom apps for Spark" connector requires a remote MCP server over **Streamable HTTP**, gated by **OAuth 2.1** -- it does not support stdio or any bearer-token/API-key field. This fork adds exactly that as a second entrypoint, alongside (not instead of) the stdio one used above.

The OAuth server here is intentionally minimal: single-user, gated by **one passphrase** you set yourself, with **no Dynamic Client Registration** -- clients are pre-registered with the `register-client` CLI command instead. This is deliberately simpler than a full identity system, appropriate for a server with exactly one owner.

### 1. Deploy

The included `render.yaml` blueprint deploys to [Render](https://render.com) as two free-plan services, no credit card: the `Dockerfile` as a web service, and a Key Value (Redis-protocol) instance holding OAuth state and the recipe cache -- Render's free web-service disk is ephemeral, so neither can live on local disk. See [`render.yaml`](render.yaml) for exactly what's declared.

1. In the Render dashboard: **New → Blueprint**, point it at this repo, and deploy. `REDIS_URL` is wired between the two services automatically -- nothing to copy by hand.
2. Once the web service exists, set its remaining env vars (Render dashboard → the `paprika-mcp` service → Environment): `PUBLIC_BASE_URL` (its own public URL, e.g. `https://paprika-mcp.onrender.com`, no trailing slash), `MCP_PASSPHRASE` (a strong passphrase you choose), `JWT_SECRET` (a random 32+ byte secret), `PAPRIKA_EMAIL`, `PAPRIKA_PASSWORD`, and `PAPRIKA_USER_AGENT` (see below). Redeploy after setting these.

**`PAPRIKA_USER_AGENT`**: `paprika_recipes`' User-Agent auto-detection reads the installed Paprika.app on macOS, which doesn't exist in a container. Get the string once from a Mac with Paprika installed:

```bash
python3 -c "
import plistlib, platform
from pathlib import Path
p = Path('/Applications/Paprika Recipe Manager 3.app/Contents/Info.plist')
with open(p, 'rb') as f:
    plist = plistlib.load(f)
print(f\"Paprika Recipe Manager 3/{plist['CFBundleShortVersionString']} \"
      f\"({plist['CFBundleIdentifier']}; build:{plist['CFBundleVersion']}; \"
      f\"macOS {platform.mac_ver()[0]})\")
"
```

and set it as a literal string env var (not auto-detected at runtime, since the container has no Paprika.app to read).

**Accepted tradeoff**: Render's free Key Value has no documented restart guarantee (see [`http/store.py`](src/paprika_mcp/http/store.py)'s module docstring). If it ever resets, redo step 2 below and re-authorize once in Gemini -- your actual Paprika data is never at risk, only this server's own session state and recipe cache, both cheaply rebuilt. A genuinely durable alternative (e.g. Upstash Redis) was considered and deliberately not used, to stay on one vendor.

**Cold starts**: Render's free web service sleeps after 15 minutes idle (~1 min to wake). [`.github/workflows/keep-warm.yml`](.github/workflows/keep-warm.yml) pings `/healthz` every 10 minutes to avoid this -- set the `PAPRIKA_MCP_URL` repository variable (Settings → Secrets and variables → Actions → Variables) to your deployed URL to enable it.

### 2. Register a client

Run once, against the deployed environment -- e.g. via Render's dashboard shell for the `paprika-mcp` service (so it reaches the same internal Key Value instance):

```bash
paprika-mcp register-client --redirect-uri "<redirect URI Gemini shows you>" --name "Gemini"
```

This prints a Client ID and Client Secret **once** -- copy them immediately.

### 3. Connect Gemini

In the Gemini app: **Settings & help → Connected Apps → Custom apps for Spark → Add a custom app**, and enter your server's `/mcp` URL (e.g. `https://paprika-mcp.onrender.com/mcp`). Gemini does not offer Dynamic Client Registration for this connector, so it will show **Advanced features → Show more** asking for OAuth credentials -- note the redirect URI it displays, register a client for that exact URI (step 2), and paste in the Client ID/Secret. Authorizing then just asks for your passphrase.

Requires a personal (non-Workspace) Google account; Google documents this connector as US-only, 18+, with Keep Activity enabled.

### Local testing

Render's free Key Value instance doesn't support external connections at all -- it's Render-internal only -- so local development runs against a real local Redis/Valkey container instead of a cloud one, over the exact same code path:

```bash
docker run -d --name paprika-dev-redis -p 6379:6379 valkey/valkey:8

PUBLIC_BASE_URL=http://127.0.0.1:8000 \
MCP_PASSPHRASE=test-pass \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))') \
REDIS_URL=redis://localhost:6379 \
paprika-mcp serve
```

then point [MCP Inspector](https://github.com/modelcontextprotocol/inspector) (`npx @modelcontextprotocol/inspector@latest`) at `http://127.0.0.1:8000/mcp` and walk the OAuth flow (register a test client first, as in step 2, with `REDIS_URL=redis://localhost:6379` set the same way).

### Code Changes and Rebuilding

The package is installed in **editable mode** (`pip install -e .`), so:

- **✓ No rebuild needed**: Changes to `.py` files are immediately available
- **⚠️ Restart required**: MCP clients cache the stdio process - restart VS Code or your MCP client to pick up changes
- **↻ Reinstall needed**: Only for `pyproject.toml` or entry point changes

Force reinstall if needed:
```bash
.venv/bin/pip install -e . --force-reinstall --no-deps
```

### Pre-commit Hooks

Pre-commit hooks run automatically via Husky when you commit. They:
1. Only run on staged Python files
2. Run isort, black, and ruff
3. Auto-fix issues and re-stage files

To install hooks manually:
```bash
npm install
```

## Security Notes

- Stdio transport: credentials are stored in plain text in `~/.paprika-mcp/config.json`; environment variables (`PAPRIKA_EMAIL`, `PAPRIKA_PASSWORD`) are also supported.
- Remote (HTTP) transport: `/authorize` is gated by `MCP_PASSPHRASE`; client secrets and refresh tokens are stored only as SHA-256 hashes in Redis; access tokens are short-lived signed JWTs; refresh tokens rotate on use, and reusing a consumed refresh token revokes the client's whole token family. See [`src/paprika_mcp/http/oauth.py`](src/paprika_mcp/http/oauth.py) for the full flow, and [`src/paprika_mcp/http/store.py`](src/paprika_mcp/http/store.py) for why Render's free Key Value's lack of a durability guarantee was an accepted tradeoff rather than an oversight.

## License

MIT

## Credits

Built on top of [paprika-recipes](https://github.com/briantkatch/paprika-recipes) originally by Adam Coddington.
