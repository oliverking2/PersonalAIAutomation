"""Notion API endpoints for managing goals."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.dependencies import get_goals_data_source_id, get_notion_client
from src.api.notion.goals.models import (
    GoalCreateRequest,
    GoalQueryRequest,
    GoalQueryResponse,
    GoalResponse,
    GoalUpdateRequest,
)
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError
from src.notion.models import NotionGoal
from src.notion.parser import build_goal_properties, parse_page_to_goal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/goals", tags=["Notion - Goals"])


@router.post(
    "/query",
    response_model=GoalQueryResponse,
    summary="Query goals",
)
def query_goals(
    request: GoalQueryRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_goals_data_source_id),
) -> GoalQueryResponse:
    """Query all goals from the configured goals tracker."""
    logger.debug("Querying goals")
    try:
        pages_data = client.query_all_data_source(
            data_source_id,
            filter_=request.filter,
            sorts=request.sorts,
        )
        goals = [_goal_to_response(parse_page_to_goal(page)) for page in pages_data]
        return GoalQueryResponse(results=goals)
    except NotionClientError as e:
        logger.exception(f"Failed to query goals: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/{goal_id}",
    response_model=GoalResponse,
    summary="Get goal",
)
def get_goal(
    goal_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> GoalResponse:
    """Retrieve a single goal."""
    logger.debug(f"Retrieving goal: {goal_id}")
    try:
        data = client.get_page(goal_id)
        goal = parse_page_to_goal(data)
        return _goal_to_response(goal)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve goal: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create goal",
)
def create_goal(
    request: GoalCreateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_goals_data_source_id),
) -> GoalResponse:
    """Create a new goal in the goals tracker."""
    logger.debug("Creating goal")
    try:
        properties = build_goal_properties(
            goal_name=request.goal_name,
            status=request.status,
            priority=request.priority,
            progress=request.progress,
            due_date=request.due_date,
        )
        data = client.create_page(
            data_source_id=data_source_id,
            properties=properties,
        )
        goal = parse_page_to_goal(data)
        return _goal_to_response(goal)
    except NotionClientError as e:
        logger.exception(f"Failed to create goal: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.patch(
    "/{goal_id}",
    response_model=GoalResponse,
    summary="Update goal",
)
def update_goal(
    goal_id: str,
    request: GoalUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
) -> GoalResponse:
    """Update a goal's properties."""
    logger.debug(f"Updating goal: {goal_id}")
    try:
        properties = build_goal_properties(
            goal_name=request.goal_name,
            status=request.status,
            priority=request.priority,
            progress=request.progress,
            due_date=request.due_date,
        )

        if not properties:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties to update.",
            )

        data = client.update_page(page_id=goal_id, properties=properties)
        goal = parse_page_to_goal(data)
        return _goal_to_response(goal)
    except NotionClientError as e:
        logger.exception(f"Failed to update goal: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _goal_to_response(goal: NotionGoal) -> GoalResponse:
    """Convert a NotionGoal to a GoalResponse."""
    return GoalResponse(
        id=goal.id,
        goal_name=goal.goal_name,
        status=goal.status,
        priority=goal.priority,
        progress=goal.progress,
        due_date=goal.due_date,
        url=goal.url,
    )
