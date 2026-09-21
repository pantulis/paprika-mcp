"""Add groceries tool - adds items to a grocery list."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote


async def add_groceries_tool(args: dict[str, Any]) -> list[TextContent]:
    """Add one or more items to a grocery list. Requires user confirmation."""
    item_names = args.get("items")
    if not item_names:
        return [
            TextContent(type="text", text="Error: 'items' must be a non-empty list")
        ]

    list_name = args.get("list_name")
    remote = get_remote()

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

    items = [{"name": name} for name in item_names]

    try:
        paprika_api.add_groceries(remote, items, list_uid)
        added = "\n".join(f"  - {name}" for name in item_names)
        return [
            TextContent(
                type="text",
                text=f"Added {len(item_names)} item(s) to your grocery list:\n{added}",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error adding groceries: {str(e)}")]


# Tool definition
TOOL_DEFINITION = {
    "name": "add_groceries",
    "description": (
        "Add one or more items to a Paprika grocery list. This is a WRITE "
        "operation that requires user confirmation. Adds to the default list "
        "unless 'list_name' is given. To add a recipe's own ingredients, use "
        "'add_recipe_to_grocery_list' instead."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Item names to add, e.g. ['milk', 'eggs', 'flour']",
            },
            "list_name": {
                "type": "string",
                "description": "Grocery list to add to by name (default: the default list)",
            },
        },
        "required": ["items"],
    },
}
