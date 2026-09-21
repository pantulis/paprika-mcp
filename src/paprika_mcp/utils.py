"""Utility functions for paprika-mcp server."""

import json
import logging
import os
import unicodedata
from typing import Any

import requests
from paprika_recipes.cache import Cache, DirectoryCache
from paprika_recipes.exceptions import PaprikaError, RequestError
from paprika_recipes.remote import Remote

from .paprika_cache import RedisCache

logger = logging.getLogger(__name__)

# Module-level cache for categories (persists for server lifetime)
_categories_cache: dict[str, dict[str, str]] | None = None


def get_credentials() -> tuple[str, str]:
    """Get Paprika credentials from environment variables or config file.

    Priority:
    1. PAPRIKA_EMAIL and PAPRIKA_PASSWORD environment variables
    2. ~/.paprika-mcp/config.json file

    Raises:
        ValueError: If credentials are not configured
    """
    # Check environment variables first
    email = os.environ.get("PAPRIKA_EMAIL")
    password = os.environ.get("PAPRIKA_PASSWORD")

    if email and password:
        return email, password

    # Check config file
    config_path = os.path.expanduser("~/.paprika-mcp/config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
                email = config.get("email")
                password = config.get("password")
                if email and password:
                    return email, password
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read config file: {e}")

    raise ValueError(
        "Paprika credentials not found. Set PAPRIKA_EMAIL and PAPRIKA_PASSWORD "
        "environment variables, or create ~/.paprika-mcp/config.json with "
        '{"email": "your@email.com", "password": "yourpassword"}'
    )


def get_user_agent() -> str | None:
    """Get User-Agent string from environment or config file.

    Priority:
    1. PAPRIKA_USER_AGENT environment variable
    2. user_agent field in ~/.paprika-mcp/config.json

    Note: If not configured here, the Remote class will auto-detect from
    the installed Paprika app.

    Returns:
        User-Agent string or None (which triggers auto-detection in Remote)
    """
    # Check environment variable first
    user_agent = os.environ.get("PAPRIKA_USER_AGENT")
    if user_agent:
        return user_agent

    # Check config file
    config_path = os.path.expanduser("~/.paprika-mcp/config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
                user_agent = config.get("user_agent")
                if user_agent:
                    return user_agent
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read user_agent from config file: {e}")

    return None


def get_recipe_cache() -> Cache:
    """Get the recipe cache backend for `Remote`.

    If `REDIS_URL` is set (the remote HTTP transport on Render), uses
    `RedisCache` -- Render's free web-service disk is ephemeral, so a local
    `DirectoryCache` there would turn every cold start into a full re-fetch
    of every recipe. Otherwise (local/stdio use) falls back to the local
    `DirectoryCache`, where a persistent disk is the normal expectation.
    """
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        return RedisCache(redis_url)

    cache_dir = os.path.expanduser("~/.paprika-mcp/cache")
    os.makedirs(cache_dir, exist_ok=True)
    return DirectoryCache(cache_dir)


def get_remote() -> Remote:
    """Get authenticated Remote instance using stored credentials.

    The Remote class uses a Cache (see `get_recipe_cache`) to store recipe
    data locally or in Redis:
    - Recipe metadata (list of UIDs/hashes) is always fetched fresh from the API
    - Individual recipe details are cached, keyed by UID and validated by hash
    - If a recipe's hash matches the cache, the cached version is used
    - If hash differs or not cached, recipe is fetched from API and cached

    Note: Remote.recipes is a generator that makes API calls. If you need to
    iterate multiple times or access by index, convert to list first.

    Raises:
        ValueError: If credentials are not configured
        PaprikaError: If authentication fails (check credentials)
        RequestError: If API request fails (network/server issue)
    """
    email, password = get_credentials()
    user_agent = get_user_agent()
    cache = get_recipe_cache()

    try:
        # Use 30 second timeout to prevent hanging on network issues
        remote = Remote(email, password, cache=cache, user_agent=user_agent, timeout=30)
        # Test authentication by accessing bearer_token
        _ = remote.bearer_token
        return remote
    except (PaprikaError, RequestError) as e:
        api_msg = str(e) or "unknown error"
        raise type(e)(
            f"Paprika authentication failed: {api_msg}. "
            "Verify email and password in ~/.paprika-mcp/config.json "
            "or PAPRIKA_EMAIL/PAPRIKA_PASSWORD environment variables."
        ) from e
    except Exception as e:
        logger.error(f"Failed to connect to Paprika API: {e}", exc_info=True)
        raise


def get_categories(bearer_token: str) -> dict[str, Any]:
    """Get all categories from Paprika API with caching.

    Returns a dict with:
    - 'uid_to_name': mapping of UUID to category name
    - 'name_to_uid': mapping of lowercase name to UUID
    - 'all': list of all category dicts
    - 'by_uid': mapping of UUID to full category dict

    Results are cached for the lifetime of the server process.
    """
    global _categories_cache

    # Return cached version if available
    if _categories_cache is not None:
        return _categories_cache

    # Fetch from API
    headers = {"Authorization": f"Bearer {bearer_token}"}
    try:
        resp = requests.get(
            "https://www.paprikaapp.com/api/v2/sync/categories/",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        categories = data.get("result", [])

        # Build mappings
        uid_to_name = {}
        name_to_uid = {}
        by_uid = {}

        for cat in categories:
            uid = cat["uid"]
            name = cat.get("name", "")
            if name:
                uid_to_name[uid] = name
                name_to_uid[name.lower()] = uid
                by_uid[uid] = cat

        _categories_cache = {
            "uid_to_name": uid_to_name,
            "name_to_uid": name_to_uid,
            "all": categories,
            "by_uid": by_uid,
        }

        return _categories_cache

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch categories: {e}")
        # Return empty mappings on error
        return {
            "uid_to_name": {},
            "name_to_uid": {},
            "all": [],
            "by_uid": {},
        }


def translate_category_uids(uids: list[str], bearer_token: str) -> str:
    """Translate a list of category UUIDs to comma-separated names.

    Args:
        uids: List of category UUIDs
        bearer_token: Paprika API bearer token

    Returns:
        Comma-separated string of category names
    """
    if not uids:
        return ""

    categories = get_categories(bearer_token)
    uid_to_name = categories["uid_to_name"]

    names = [uid_to_name.get(uid, f"Unknown-{uid[:8]}") for uid in uids]
    return ", ".join(names)


def normalize_string(text: str) -> str:
    """Normalize unicode string for comparison.

    Uses NFD normalization to decompose accented characters,
    making comparisons work across different unicode representations.
    """
    return unicodedata.normalize("NFD", text).lower()


def search_in_text(
    text: str, query: str, context_lines: int = 2, regex: bool = False
) -> list[dict[str, Any]]:
    """Search for query in text and return matches with context.

    Args:
        text: Text to search in
        query: Search query (plain text or regex pattern)
        context_lines: Number of lines of context around matches
        regex: If True, treat query as a regex pattern

    Returns list of dicts with 'line', 'match', and 'context' keys.
    """
    if not text:
        return []

    matches = []
    lines = text.split("\n")

    if regex:
        import re

        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            # Invalid regex - return empty results
            logger.warning(f"Invalid regex pattern '{query}': {e}")
            return []

        for i, line in enumerate(lines):
            if pattern.search(line):
                # Get context lines before and after
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = "\n".join(lines[start:end])

                matches.append(
                    {"line": i + 1, "match": line.strip(), "context": context}
                )
    else:
        query_lower = query.lower()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # Get context lines before and after
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = "\n".join(lines[start:end])

                matches.append(
                    {"line": i + 1, "match": line.strip(), "context": context}
                )

    return matches
