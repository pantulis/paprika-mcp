"""Add recipe to grocery list tool - adds a recipe's ingredients to your list."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote, normalize_string


async def add_recipe_to_grocery_list_tool(args: dict[str, Any]) -> list[TextContent]:
    """Add all of a recipe's ingredients to a grocery list. Requires confirmation."""
    recipe_id = args.get("id")
    recipe_title = args.get("title")
    list_name = args.get("list_name")

    if not recipe_id and not recipe_title:
        return [
            TextContent(type="text", text="Error: Must provide either 'id' or 'title'")
        ]

    remote = get_remote()

    recipe = None
    if recipe_id:
        for r in remote.recipes:
            if r.uid == recipe_id:
                recipe = r
                break
    else:
        normalized_search = normalize_string(recipe_title)
        for r in remote.recipes:
            if normalize_string(r.name) == normalized_search:
                recipe = r
                break

    if not recipe:
        identifier = recipe_id or recipe_title
        return [
            TextContent(
                type="text", text=f"Error: No recipe found matching '{identifier}'"
            )
        ]

    if not recipe.ingredients or not recipe.ingredients.strip():
        return [
            TextContent(
                type="text", text=f"Recipe '{recipe.name}' has no ingredients to add."
            )
        ]

    ingredient_lines = [
        line.strip() for line in recipe.ingredients.split("\n") if line.strip()
    ]

    if list_name:
        lists = paprika_api.list_grocery_lists(remote)
        matches = [
            lst for lst in lists if lst.get("name", "").lower() == list_name.lower()
        ]
        if not matches:
            names = ", ".join(lst.get("name", "") for lst in lists)
            return [
                TextContent(
                    type="text",
                    text=f"Error: No grocery list named '{list_name}'. Available: {names}",
                )
            ]
        list_uid = matches[0]["uid"]
    else:
        list_uid = paprika_api.get_default_grocery_list_uid(remote)
        if not list_uid:
            return [
                TextContent(
                    type="text",
                    text="Error: No grocery lists found in your Paprika account.",
                )
            ]

    items = [
        {"name": line, "recipe_uid": recipe.uid, "recipe": recipe.name}
        for line in ingredient_lines
    ]

    try:
        paprika_api.add_groceries(remote, items, list_uid)
        added = "\n".join(f"  - {line}" for line in ingredient_lines)
        return [
            TextContent(
                type="text",
                text=(
                    f"Added {len(ingredient_lines)} ingredient(s) from "
                    f"'{recipe.name}' to your grocery list:\n{added}"
                ),
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error adding ingredients: {str(e)}")]


# Tool definition
TOOL_DEFINITION = {
    "name": "add_recipe_to_grocery_list",
    "description": (
        "Add all of a recipe's ingredients to a Paprika grocery list, one item "
        "per ingredient line. This is a WRITE operation that requires user "
        "confirmation. Identify the recipe by 'id' or exact 'title'."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Recipe UID"},
            "title": {
                "type": "string",
                "description": "Exact recipe title (alternative to id)",
            },
            "list_name": {
                "type": "string",
                "description": "Grocery list to add to by name (default: the default list)",
            },
        },
        "required": [],
    },
}
