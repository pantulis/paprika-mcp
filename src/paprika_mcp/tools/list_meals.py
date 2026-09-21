"""List meals tool - shows meal plan entries."""

from typing import Any

from mcp.types import TextContent

from .. import paprika_api
from ..utils import get_remote


async def list_meals_tool(args: dict[str, Any]) -> list[TextContent]:
    """List meal plan entries, optionally filtered to a date range."""
    start_date = args.get("start_date")
    end_date = args.get("end_date")

    remote = get_remote()
    meals = paprika_api.list_meals(remote, start_date, end_date)
    meals = [m for m in meals if not m.get("deleted")]

    if not meals:
        return [
            TextContent(type="text", text="No meal plan entries found for that range.")
        ]

    meals.sort(key=lambda m: (m.get("date") or "", m.get("type", 0)))

    lines = [f"Found {len(meals)} meal plan entr{'y' if len(meals) == 1 else 'ies'}:\n"]
    for meal in meals:
        date = (meal.get("date") or "")[:10]
        meal_type = paprika_api.MEAL_TYPE_NAMES.get(meal.get("type", -1), "unknown")
        title = meal.get("name") or "(untitled)"
        recipe_note = (
            f" [recipe: {meal['recipe_uid']}]" if meal.get("recipe_uid") else ""
        )
        lines.append(f"- {date} {meal_type}: {title}{recipe_note} (ID: {meal['uid']})")

    return [TextContent(type="text", text="\n".join(lines))]


# Tool definition
TOOL_DEFINITION = {
    "name": "list_meals",
    "description": (
        "List meal plan entries, optionally filtered to a date range. "
        "Dates are 'YYYY-MM-DD'; both start_date and end_date are inclusive "
        "and optional."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Earliest date to include, YYYY-MM-DD",
            },
            "end_date": {
                "type": "string",
                "description": "Latest date to include, YYYY-MM-DD",
            },
        },
        "required": [],
    },
}
