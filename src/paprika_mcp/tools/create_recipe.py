"""Create recipe tool - adds a new recipe to Paprika."""

from typing import Any

from mcp.types import TextContent
from paprika_recipes.remote import RemoteRecipe

from ..utils import get_categories, get_remote


async def create_recipe_tool(args: dict[str, Any]) -> list[TextContent]:
    """Create a new recipe. This is a WRITE operation requiring confirmation."""
    name = args["name"]
    category_names = args.get("categories", [])

    remote = get_remote()

    # Categories are stored as category UUIDs on the recipe (see update_recipe.py),
    # but users and the model should work with names.
    category_uids = []
    if category_names:
        categories_info = get_categories(remote.bearer_token)
        name_to_uid = categories_info["name_to_uid"]
        unknown = [c for c in category_names if c.lower() not in name_to_uid]
        if unknown:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Error: Unknown categories: {', '.join(unknown)}. "
                        "Use list_categories to see valid names. No recipe was created."
                    ),
                )
            ]
        category_uids = [name_to_uid[c.lower()] for c in category_names]

    recipe = RemoteRecipe(
        name=name,
        ingredients=args.get("ingredients", ""),
        directions=args.get("directions", ""),
        categories=category_uids,
        description=args.get("description", ""),
        notes=args.get("notes", ""),
        source=args.get("source", ""),
        source_url=args.get("source_url", ""),
        prep_time=args.get("prep_time", ""),
        cook_time=args.get("cook_time", ""),
        total_time=args.get("total_time", ""),
        servings=args.get("servings", ""),
        difficulty=args.get("difficulty", ""),
        rating=args.get("rating", 0),
        nutritional_info=args.get("nutritional_info", ""),
    )

    try:
        created = remote.upload_recipe(recipe)
        return [
            TextContent(
                type="text",
                text=f"Successfully created recipe '{created.name}' (ID: {created.uid})",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating recipe: {str(e)}")]


# Tool definition
TOOL_DEFINITION = {
    "name": "create_recipe",
    "description": (
        "Create a new recipe in Paprika. This is a WRITE operation that requires "
        "user confirmation. Only 'name' is required; all other fields are optional. "
        "Use category NAMES (not UUIDs) -- they're resolved automatically. "
        "Use list_categories first to see valid category names."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Recipe title (required)"},
            "ingredients": {
                "type": "string",
                "description": "Newline-separated ingredient list",
            },
            "directions": {
                "type": "string",
                "description": "Step-by-step cooking instructions",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category names to assign (not UUIDs)",
            },
            "description": {"type": "string", "description": "Recipe summary"},
            "notes": {"type": "string", "description": "Additional notes"},
            "source": {"type": "string", "description": "Attribution / source name"},
            "source_url": {"type": "string", "description": "Original recipe URL"},
            "prep_time": {"type": "string", "description": "Preparation duration"},
            "cook_time": {"type": "string", "description": "Cooking duration"},
            "total_time": {"type": "string", "description": "Total time"},
            "servings": {
                "type": "string",
                "description": "Serving quantity (free text)",
            },
            "difficulty": {"type": "string", "description": "Recipe complexity level"},
            "rating": {
                "type": "integer",
                "description": "Star rating, 0-5",
                "default": 0,
            },
            "nutritional_info": {"type": "string", "description": "Nutritional data"},
        },
        "required": ["name"],
    },
}
