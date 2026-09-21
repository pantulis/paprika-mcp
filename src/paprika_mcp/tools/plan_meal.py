"""Plan meal tool - adds an entry to the meal plan."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote, normalize_string


async def plan_meal_tool(args: dict[str, Any]) -> list[TextContent]:
    """Add a meal plan entry. Requires user confirmation."""
    date = args["date"]
    meal_type = args["meal_type"]
    recipe_id = args.get("recipe_id")
    recipe_title = args.get("recipe_title")
    name = args.get("name")

    if meal_type not in paprika_api.MEAL_TYPES:
        return [
            TextContent(
                type="text",
                text=f"Error: meal_type must be one of {sorted(paprika_api.MEAL_TYPES)}",
            )
        ]

    remote = get_remote()

    resolved_recipe_uid = recipe_id
    display_name = name

    if recipe_title and not recipe_id:
        normalized_search = normalize_string(recipe_title)
        recipe = None
        for r in remote.recipes:
            if normalize_string(r.name) == normalized_search:
                recipe = r
                break
        if not recipe:
            return [
                TextContent(
                    type="text",
                    text=f"Error: No recipe found with title '{recipe_title}'",
                )
            ]
        resolved_recipe_uid = recipe.uid
        display_name = display_name or recipe.name

    if not resolved_recipe_uid and not display_name:
        return [
            TextContent(
                type="text",
                text="Error: Must provide recipe_id, recipe_title, or name",
            )
        ]

    try:
        paprika_api.plan_meal(
            remote,
            date=date,
            meal_type=meal_type,
            recipe_uid=resolved_recipe_uid,
            name=display_name,
        )
        label = display_name or resolved_recipe_uid
        return [
            TextContent(
                type="text", text=f"Planned '{label}' for {meal_type} on {date}."
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error planning meal: {str(e)}")]


# Tool definition
TOOL_DEFINITION = {
    "name": "plan_meal",
    "description": (
        "Add an entry to the Paprika meal plan for a given date and meal type. "
        "This is a WRITE operation that requires user confirmation. Link an "
        "existing recipe with 'recipe_id' or 'recipe_title', or plan a "
        "text-only meal with 'name'."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            "meal_type": {
                "type": "string",
                "enum": ["breakfast", "lunch", "dinner", "snack"],
                "description": "Which meal slot to plan",
            },
            "recipe_id": {"type": "string", "description": "Recipe UID to link"},
            "recipe_title": {
                "type": "string",
                "description": "Exact recipe title to link (alternative to recipe_id)",
            },
            "name": {
                "type": "string",
                "description": (
                    "Text-only meal name, used when not linking a recipe "
                    "(or to override the display name for a linked recipe)"
                ),
            },
        },
        "required": ["date", "meal_type"],
    },
}
