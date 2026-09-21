"""Trash recipe tool - soft-deletes a recipe (Paprika has no hard delete)."""

from typing import Any

from mcp.types import TextContent

from ..utils import get_remote


async def trash_recipe_tool(args: dict[str, Any]) -> list[TextContent]:
    """Move a recipe to trash. DANGEROUS - requires user confirmation."""
    recipe_id = args["id"]

    remote = get_remote()

    recipe = None
    for r in remote.recipes:
        if r.uid == recipe_id:
            recipe = r
            break

    if not recipe:
        return [
            TextContent(
                type="text", text=f"Error: No recipe found with ID '{recipe_id}'"
            )
        ]

    if recipe.in_trash:
        return [
            TextContent(
                type="text", text=f"Recipe '{recipe.name}' is already in trash."
            )
        ]

    recipe.in_trash = True
    try:
        remote.upload_recipe(recipe)
        return [
            TextContent(
                type="text",
                text=(
                    f"Moved recipe '{recipe.name}' (ID: {recipe_id}) to trash. "
                    "Paprika has no permanent delete via the API; restore it from "
                    "within the Paprika app if needed."
                ),
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text", text=f"Error trashing recipe '{recipe.name}': {str(e)}"
            )
        ]


# Tool definition
TOOL_DEFINITION = {
    "name": "trash_recipe",
    "description": (
        "Move a recipe to trash (soft delete). This is a DANGEROUS operation that "
        "requires user confirmation. Paprika has no permanent delete via the API; "
        "trashed recipes can be restored from within the Paprika app."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Recipe UID to trash"},
        },
        "required": ["id"],
    },
}
