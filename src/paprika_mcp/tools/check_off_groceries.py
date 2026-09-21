"""Check off groceries tool - marks grocery items purchased (or unpurchased)."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote


async def check_off_groceries_tool(args: dict[str, Any]) -> list[TextContent]:
    """Mark grocery items purchased/unpurchased by ID. Requires confirmation."""
    item_ids = args.get("ids")
    if not item_ids:
        return [TextContent(type="text", text="Error: 'ids' must be a non-empty list")]

    purchased = args.get("purchased", True)

    remote = get_remote()
    all_items = paprika_api.list_groceries(remote)
    items_by_uid = {item["uid"]: item for item in all_items}

    targets = []
    missing = []
    for item_id in item_ids:
        item = items_by_uid.get(item_id)
        if item:
            targets.append(item)
        else:
            missing.append(item_id)

    if missing:
        return [
            TextContent(
                type="text",
                text=(
                    f"Error: No grocery item(s) found with ID(s): {', '.join(missing)}. "
                    "No changes were made."
                ),
            )
        ]

    try:
        paprika_api.check_off_groceries(remote, targets, purchased=purchased)
        names = "\n".join(f"  - {item['name']}" for item in targets)
        verb = "Checked off" if purchased else "Unchecked"
        return [
            TextContent(type="text", text=f"{verb} {len(targets)} item(s):\n{names}")
        ]
    except Exception as e:
        return [
            TextContent(type="text", text=f"Error updating grocery items: {str(e)}")
        ]


# Tool definition
TOOL_DEFINITION = {
    "name": "check_off_groceries",
    "description": (
        "Mark grocery items as purchased (checked off) or unpurchased. This is "
        "a WRITE operation that requires user confirmation. Paprika has no hard "
        "delete for grocery items -- checking an item off is how you clear it. "
        "Use list_groceries first to find item IDs."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Grocery item UIDs to update",
            },
            "purchased": {
                "type": "boolean",
                "description": "true to check off (default), false to uncheck",
                "default": True,
            },
        },
        "required": ["ids"],
    },
}
