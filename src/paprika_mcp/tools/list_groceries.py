"""List groceries tool - shows items on your grocery list(s)."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote


async def list_groceries_tool(args: dict[str, Any]) -> list[TextContent]:
    """List grocery items, optionally filtered to one list and/or unpurchased-only."""
    include_purchased = args.get("include_purchased", False)
    list_name = args.get("list_name")

    remote = get_remote()
    lists = paprika_api.list_grocery_lists(remote)
    items = paprika_api.list_groceries(remote)

    lists_by_uid = {lst["uid"]: lst for lst in lists}

    if list_name:
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
        target_list_uid = matches[0]["uid"]
        items = [i for i in items if i.get("list_uid") == target_list_uid]

    if not include_purchased:
        items = [i for i in items if not i.get("purchased")]

    if not items:
        return [TextContent(type="text", text="No grocery items found.")]

    items.sort(key=lambda i: (bool(i.get("purchased")), (i.get("name") or "").lower()))

    lines = [f"Found {len(items)} grocery item(s):\n"]
    for item in items:
        list_label = lists_by_uid.get(item.get("list_uid", ""), {}).get(
            "name", "Unknown list"
        )
        checkbox = "[x]" if item.get("purchased") else "[ ]"
        qty = f" ({item['quantity']})" if item.get("quantity") else ""
        lines.append(
            f"{checkbox} {item.get('name', '')}{qty} - {list_label} (ID: {item['uid']})"
        )

    return [TextContent(type="text", text="\n".join(lines))]


# Tool definition
TOOL_DEFINITION = {
    "name": "list_groceries",
    "description": (
        "List items on your Paprika grocery list(s). By default shows only "
        "unpurchased items across all lists; use 'list_name' to filter to one "
        "list, and 'include_purchased' to also show checked-off items."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "list_name": {
                "type": "string",
                "description": "Filter to a specific grocery list by name (optional)",
            },
            "include_purchased": {
                "type": "boolean",
                "description": "Include already-purchased/checked items (default: false)",
                "default": False,
            },
        },
        "required": [],
    },
}
