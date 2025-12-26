"""Goals tool handlers for the AI agent.

These tools are thin wrappers around the API endpoints. All business logic,
validation, and Notion interaction is handled by the API layer.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.agent.api_client import AgentAPIClient
from src.agent.enums import RiskLevel
from src.agent.models import ToolDef
from src.api.notion.goals.models import (
    GoalCreateRequest,
    GoalQueryRequest,
    GoalUpdateRequest,
)
from src.notion.enums import GoalStatus, Priority

logger = logging.getLogger(__name__)


def _get_client() -> AgentAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return AgentAPIClient()


# --- Argument Models ---
# Only define models for tool-specific arguments not covered by API models.


class GetGoalArgs(BaseModel):
    """Arguments for getting a goal by ID."""

    goal_id: str = Field(..., min_length=1, description="The Notion page ID of the goal")


class UpdateGoalArgs(GoalUpdateRequest):
    """Arguments for updating a goal (extends API model with goal_id)."""

    goal_id: str = Field(..., min_length=1, description="The Notion page ID to update")


# --- Tool Handlers ---


def query_goals(args: GoalQueryRequest) -> dict[str, Any]:
    """Query goals via API.

    :param args: Query arguments with optional filters.
    :returns: Dictionary with 'items' list and 'count'.
    """
    logger.debug(f"Querying goals: status={args.status}, priority={args.priority}")

    with _get_client() as client:
        response = client.post(
            "/notion/goals/query",
            json=args.model_dump(mode="json", exclude_none=True),
        )

    items = response.get("results", [])
    return {"items": items, "count": len(items)}


def get_goal(args: GetGoalArgs) -> dict[str, Any]:
    """Get a single goal by ID via API.

    :param args: Arguments containing the goal ID.
    :returns: Dictionary with the goal details.
    """
    logger.debug(f"Getting goal: {args.goal_id}")

    with _get_client() as client:
        response = client.get(f"/notion/goals/{args.goal_id}")

    return {"item": response}


def create_goal(args: GoalCreateRequest) -> dict[str, Any]:
    """Create a new goal via API.

    :param args: Arguments for the new goal.
    :returns: Dictionary with the created goal details.
    """
    logger.debug(f"Creating goal: {args.goal_name}")

    with _get_client() as client:
        response = client.post(
            "/notion/goals",
            json=args.model_dump(mode="json", exclude_none=True),
        )

    return {"item": response, "created": True}


def update_goal(args: UpdateGoalArgs) -> dict[str, Any]:
    """Update an existing goal via API.

    :param args: Arguments for the update.
    :returns: Dictionary with the updated goal details.
    """
    logger.debug(f"Updating goal: {args.goal_id}")

    # Exclude goal_id from the payload (it's in the URL)
    payload = args.model_dump(mode="json", exclude_none=True, exclude={"goal_id"})

    if not payload:
        return {"error": "No properties to update", "updated": False}

    with _get_client() as client:
        response = client.patch(f"/notion/goals/{args.goal_id}", json=payload)

    return {"item": response, "updated": True}


# --- Tool Definitions ---


def get_goals_tools() -> list[ToolDef]:
    """Get all goals tool definitions.

    :returns: List of ToolDef instances for goals operations.
    """
    # Build dynamic descriptions from enums
    status_options = ", ".join(GoalStatus)
    priority_options = ", ".join(Priority)

    return [
        ToolDef(
            name="query_goals",
            description=(
                f"Query goals from the goals tracker. Can filter by status "
                f"({status_options}) and priority ({priority_options})."
            ),
            tags=frozenset({"goals", "query", "list"}),
            risk_level=RiskLevel.SAFE,
            args_model=GoalQueryRequest,
            handler=query_goals,
        ),
        ToolDef(
            name="get_goal",
            description=(
                "Get details of a specific goal by its ID. "
                "Returns goal name, status, priority, progress, and due date."
            ),
            tags=frozenset({"goals", "get", "item"}),
            risk_level=RiskLevel.SAFE,
            args_model=GetGoalArgs,
            handler=get_goal,
        ),
        ToolDef(
            name="create_goal",
            description=(
                f"Create a new goal. Requires a goal name. "
                f"Optional: status ({status_options}), priority ({priority_options}), "
                f"progress (0-100), and due date."
            ),
            tags=frozenset({"goals", "create", "item"}),
            risk_level=RiskLevel.SAFE,
            args_model=GoalCreateRequest,
            handler=create_goal,
        ),
        ToolDef(
            name="update_goal",
            description=(
                f"Update an existing goal. Requires the goal ID. "
                f"Can update goal name, status ({status_options}), "
                f"priority ({priority_options}), progress, or due date."
            ),
            tags=frozenset({"goals", "update", "item"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=UpdateGoalArgs,
            handler=update_goal,
        ),
    ]
