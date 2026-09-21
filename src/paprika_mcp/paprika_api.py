"""Extended Paprika v2 sync API client.

`paprika_recipes.Remote` only covers recipes. This module reaches the rest of
the v2 sync API (categories, grocery lists, groceries, meals, pantry, status)
by reusing `Remote`'s already-authenticated session via its `_request` method,
which already solves login, retries, and the gzip/error-envelope quirks of
this unofficial API. `Remote._request` is a "private" method, but this project
is a fork of `paprika-recipes` maintained alongside it, so relying on it here
is an intentional, documented choice rather than an accident.

Field names below are taken from verified, dated request/response examples
(not assumed), primarily aarons22/paprika-tools' API_REFERENCE.md (verified
live against a real account, 2026-06-29) and corroborated by Matt Steele's
Paprika API gist. There is no reliable documented write schema for pantry
items anywhere, so pantry support here is read-only.

All POST endpoints require a gzip-compressed JSON **array** sent as
multipart/form-data under the field name `data` -- the same wire shape as
`Remote.upload_recipe`. Paprika has no hard delete: groceries use
`purchased: true`, meals use `deleted: true`, recipes use `in_trash: true`.
"""

from __future__ import annotations

import datetime
import gzip
import json
import uuid
from typing import Any

from paprika_recipes.remote import Remote

# Meal type as used by the API: an integer 0-3, not a free-text string.
MEAL_TYPES = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}
MEAL_TYPE_NAMES = {v: k for k, v in MEAL_TYPES.items()}


def new_uid() -> str:
    """Generate an uppercase UUID4, as Paprika expects for client-created items."""
    return str(uuid.uuid4()).upper()


def _now_str() -> str:
    """Return the current UTC time in Paprika's "YYYY-MM-DD HH:MM:SS" format."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_result(remote: Remote, path: str) -> Any:
    """GET a `/api/v2/sync/...` endpoint and unwrap the `{"result": ...}` envelope."""
    response = remote._request("get", path)  # noqa: SLF001 - see module docstring
    return response.json().get("result", [])


def _post_array(remote: Remote, path: str, payload: list[dict]) -> Any:
    """POST a gzip-compressed JSON array as multipart/form-data field `data`.

    Mirrors `Remote.upload_recipe`'s wire format, required by every Paprika
    v2 write endpoint. Never send a bare object -- writes must be arrays,
    even for a single item.
    """
    body = gzip.compress(json.dumps(payload).encode("utf-8"))
    response = remote._request(  # noqa: SLF001 - see module docstring
        "post", path, files={"data": ("file", body)}
    )
    return response.json().get("result")


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------


def list_categories(remote: Remote) -> list[dict]:
    """List all recipe categories: {uid, name, order_flag, parent_uid}."""
    return _get_result(remote, "/api/v2/sync/categories/")


# --------------------------------------------------------------------------
# Grocery lists & items
# --------------------------------------------------------------------------


def list_grocery_lists(remote: Remote) -> list[dict]:
    """List grocery lists: {uid, name, order_flag, is_default, reminders_list}."""
    return _get_result(remote, "/api/v2/sync/grocerylists/")


def list_groceries(remote: Remote) -> list[dict]:
    """List all grocery items across all lists (server returns everything;
    filter by `list_uid` client-side for a single list)."""
    return _get_result(remote, "/api/v2/sync/groceries/")


def get_default_grocery_list_uid(remote: Remote) -> str | None:
    """Find the default grocery list's uid, falling back to the first list."""
    lists = list_grocery_lists(remote)
    for lst in lists:
        if lst.get("is_default"):
            return lst.get("uid")
    return lists[0]["uid"] if lists else None


def add_groceries(remote: Remote, items: list[dict[str, Any]], list_uid: str) -> Any:
    """Add grocery items to a list.

    Each item dict may provide: name (required), quantity, instruction,
    recipe_uid, recipe (source recipe name for display). `aisle` is always
    sent empty so Paprika auto-assigns it, and `ingredient` defaults to the
    lowercased `name` when not given.
    """
    payload = []
    for item in items:
        name = item["name"]
        payload.append(
            {
                "uid": item.get("uid") or new_uid(),
                "recipe_uid": item.get("recipe_uid"),
                "name": name,
                "order_flag": item.get("order_flag", 0),
                "purchased": False,
                "aisle": "",
                "ingredient": item.get("ingredient", name.lower()),
                "recipe": item.get("recipe"),
                "instruction": item.get("instruction", ""),
                "quantity": item.get("quantity", ""),
                "separate": False,
                "list_uid": list_uid,
            }
        )
    return _post_array(remote, "/api/v2/sync/groceries/", payload)


def check_off_groceries(
    remote: Remote, items: list[dict[str, Any]], purchased: bool = True
) -> Any:
    """Mark grocery items purchased (or unpurchased). Paprika has no hard
    delete for groceries, so this is also how items are "removed".

    Each item must be the full existing item dict (from `list_groceries`)
    with `purchased` flipped -- Paprika writes replace the whole object.
    """
    payload = [{**item, "purchased": purchased} for item in items]
    return _post_array(remote, "/api/v2/sync/groceries/", payload)


# --------------------------------------------------------------------------
# Meal plan
# --------------------------------------------------------------------------


def list_meals(
    remote: Remote, start_date: str | None = None, end_date: str | None = None
) -> list[dict]:
    """List meal plan entries, optionally filtered to a `YYYY-MM-DD` range
    (inclusive). The API always returns the full plan; filtering happens
    client-side since there's no documented server-side date filter."""
    meals = _get_result(remote, "/api/v2/sync/meals/")
    if start_date:
        meals = [m for m in meals if (m.get("date") or "") >= start_date]
    if end_date:
        meals = [m for m in meals if (m.get("date") or "")[:10] <= end_date]
    return meals


def plan_meal(
    remote: Remote,
    date: str,
    meal_type: str,
    recipe_uid: str | None = None,
    name: str | None = None,
) -> Any:
    """Add a meal plan entry for `date` (YYYY-MM-DD).

    `meal_type` is one of "breakfast", "lunch", "dinner", "snack". Provide
    either `recipe_uid` (to link an existing recipe) or `name` (a
    text-only meal with no recipe link) -- at least one is required.

    `type_uid` is left as an empty string: the API's own live-verified
    example uses "" on create and the numeric `type` field is what actually
    controls the meal slot.
    """
    if meal_type not in MEAL_TYPES:
        raise ValueError(f"meal_type must be one of {sorted(MEAL_TYPES)}")
    if not recipe_uid and not name:
        raise ValueError("Must provide either recipe_uid or name")

    payload = [
        {
            "uid": new_uid(),
            "recipe_uid": recipe_uid,
            "date": f"{date} 00:00:00",
            "type": MEAL_TYPES[meal_type],
            "name": name or "",
            "order_flag": 0,
            "type_uid": "",
            "scale": None,
            "is_ingredient": False,
            "deleted": False,
        }
    ]
    return _post_array(remote, "/api/v2/sync/meals/", payload)


def remove_meal(remote: Remote, meal: dict[str, Any]) -> Any:
    """Soft-delete a meal plan entry (`deleted: true`). `meal` must be the
    full existing entry dict, as returned by `list_meals`."""
    payload = [{**meal, "deleted": True}]
    return _post_array(remote, "/api/v2/sync/meals/", payload)


# --------------------------------------------------------------------------
# Pantry (read-only: no documented write schema exists anywhere)
# --------------------------------------------------------------------------


def list_pantry(remote: Remote) -> list[dict]:
    """List pantry items. Read-only -- Paprika's pantry write schema isn't
    documented in any known source, so this module doesn't guess at it."""
    return _get_result(remote, "/api/v2/sync/pantry/")


# --------------------------------------------------------------------------
# Sync status
# --------------------------------------------------------------------------


def sync_status(remote: Remote) -> dict:
    """Return the sync status counters (recipes, categories, meals,
    groceries, pantry, etc). These are change counters, not totals."""
    response = remote._request("get", "/api/v2/sync/status/")  # noqa: SLF001
    return response.json().get("result", {})
