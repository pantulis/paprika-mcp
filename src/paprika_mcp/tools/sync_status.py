"""Sync status tool - connectivity check and change counters."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote


async def sync_status_tool(args: dict[str, Any]) -> list[TextContent]:
    """Get sync status counters. Also doubles as a connectivity/auth check."""
    remote = get_remote()
    try:
        status = paprika_api.sync_status(remote)
    except Exception as e:
        return [TextContent(type="text", text=f"Error reaching Paprika: {str(e)}")]

    if not status:
        return [
            TextContent(
                type="text", text="Connected to Paprika, but no status data returned."
            )
        ]

    lines = ["Connected to Paprika. Sync status counters:\n"]
    for key in sorted(status):
        lines.append(f"- {key}: {status[key]}")

    return [TextContent(type="text", text="\n".join(lines))]


# Tool definition
TOOL_DEFINITION = {
    "name": "sync_status",
    "description": (
        "Get Paprika sync status counters (recipes, categories, meals, "
        "groceries, pantry, etc). Values are change counters, not totals. "
        "Also useful as a simple connectivity/auth check."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
