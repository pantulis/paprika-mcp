"""Tools module - exports all MCP tool implementations."""

from .add_groceries import TOOL_DEFINITION as ADD_GROCERIES_DEF
from .add_groceries import add_groceries_tool
from .add_recipe_to_grocery_list import (
    TOOL_DEFINITION as ADD_RECIPE_TO_GROCERY_LIST_DEF,
)
from .add_recipe_to_grocery_list import add_recipe_to_grocery_list_tool
from .check_off_groceries import TOOL_DEFINITION as CHECK_OFF_GROCERIES_DEF
from .check_off_groceries import check_off_groceries_tool
from .create_recipe import TOOL_DEFINITION as CREATE_RECIPE_DEF
from .create_recipe import create_recipe_tool
from .format_fraction import TOOL_DEFINITION as FORMAT_FRACTION_DEF
from .format_fraction import format_fraction_tool
from .list_categories import TOOL_DEFINITION as LIST_CATEGORIES_DEF
from .list_categories import list_categories_tool
from .list_groceries import TOOL_DEFINITION as LIST_GROCERIES_DEF
from .list_groceries import list_groceries_tool
from .list_meals import TOOL_DEFINITION as LIST_MEALS_DEF
from .list_meals import list_meals_tool
from .list_pantry import TOOL_DEFINITION as LIST_PANTRY_DEF
from .list_pantry import list_pantry_tool
from .plan_meal import TOOL_DEFINITION as PLAN_MEAL_DEF
from .plan_meal import plan_meal_tool
from .read_recipe import TOOL_DEFINITION as READ_RECIPE_DEF
from .read_recipe import read_recipe_tool
from .search_recipes import TOOL_DEFINITION as SEARCH_RECIPES_DEF
from .search_recipes import search_recipes_tool
from .sync_status import TOOL_DEFINITION as SYNC_STATUS_DEF
from .sync_status import sync_status_tool
from .trash_recipe import TOOL_DEFINITION as TRASH_RECIPE_DEF
from .trash_recipe import trash_recipe_tool
from .update_recipe import TOOL_DEFINITION as UPDATE_RECIPE_DEF
from .update_recipe import update_recipe_tool

# Export all tools and their definitions
TOOLS = {
    # Recipes
    "search_recipes": {
        "definition": SEARCH_RECIPES_DEF,
        "handler": search_recipes_tool,
    },
    "read_recipe": {
        "definition": READ_RECIPE_DEF,
        "handler": read_recipe_tool,
    },
    "create_recipe": {
        "definition": CREATE_RECIPE_DEF,
        "handler": create_recipe_tool,
    },
    "update_recipe": {
        "definition": UPDATE_RECIPE_DEF,
        "handler": update_recipe_tool,
    },
    "trash_recipe": {
        "definition": TRASH_RECIPE_DEF,
        "handler": trash_recipe_tool,
    },
    "list_categories": {
        "definition": LIST_CATEGORIES_DEF,
        "handler": list_categories_tool,
    },
    # Groceries
    "list_groceries": {
        "definition": LIST_GROCERIES_DEF,
        "handler": list_groceries_tool,
    },
    "add_groceries": {
        "definition": ADD_GROCERIES_DEF,
        "handler": add_groceries_tool,
    },
    "add_recipe_to_grocery_list": {
        "definition": ADD_RECIPE_TO_GROCERY_LIST_DEF,
        "handler": add_recipe_to_grocery_list_tool,
    },
    "check_off_groceries": {
        "definition": CHECK_OFF_GROCERIES_DEF,
        "handler": check_off_groceries_tool,
    },
    # Meal plan
    "list_meals": {
        "definition": LIST_MEALS_DEF,
        "handler": list_meals_tool,
    },
    "plan_meal": {
        "definition": PLAN_MEAL_DEF,
        "handler": plan_meal_tool,
    },
    # Pantry
    "list_pantry": {
        "definition": LIST_PANTRY_DEF,
        "handler": list_pantry_tool,
    },
    # Ops
    "sync_status": {
        "definition": SYNC_STATUS_DEF,
        "handler": sync_status_tool,
    },
    # Utility
    "format_fraction": {
        "definition": FORMAT_FRACTION_DEF,
        "handler": format_fraction_tool,
    },
}

__all__ = [
    "TOOLS",
    "search_recipes_tool",
    "read_recipe_tool",
    "create_recipe_tool",
    "update_recipe_tool",
    "trash_recipe_tool",
    "list_categories_tool",
    "list_groceries_tool",
    "add_groceries_tool",
    "add_recipe_to_grocery_list_tool",
    "check_off_groceries_tool",
    "list_meals_tool",
    "plan_meal_tool",
    "list_pantry_tool",
    "sync_status_tool",
    "format_fraction_tool",
]
