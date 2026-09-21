"""List pantry tool - shows pantry inventory (read-only)."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote


async def list_pantry_tool(args: dict[str, Any]) -> list[TextContent]:
    """List pantry items. Read-only."""
    remote = get_remote()
    items = paprika_api.list_pantry(remote)

    if not items:
        return [TextContent(type="text", text="No pantry items found.")]

    lines = [f"Found {len(items)} pantry item(s):\n"]
    for item in items:
        name = item.get("ingredient") or item.get("name") or "(unnamed)"
        aisle = f" [{item['aisle']}]" if item.get("aisle") else ""
        lines.append(f"- {name}{aisle}")

    return [TextContent(type="text", text="\n".join(lines))]


# Tool definition
TOOL_DEFINITION = {
    "name": "list_pantry",
    "description": (
        "List items in your Paprika pantry inventory. Read-only -- Paprika's "
        "pantry write API isn't reliably documented anywhere, so pantry items "
        "can't be added or changed through this server."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
