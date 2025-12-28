"""Notion API endpoints for managing goals."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.models import BulkCreateFailure
from src.api.notion.common.utils import check_duplicate_name, filter_by_fuzzy_name
from src.api.notion.dependencies import get_goals_data_source_id, get_notion_client
from src.api.notion.goals.models import (
    GoalBulkCreateResponse,
    GoalCreateRequest,
    GoalQueryRequest,
    GoalQueryResponse,
    GoalResponse,
    GoalUpdateRequest,
)
from src.notion.blocks import blocks_to_markdown, markdown_to_blocks
from src.notion.client import NotionClient
from src.notion.enums import GoalStatus
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
    """Query goals from the configured goals tracker.

    By default, completed (Done) goals are excluded unless include_done=True.
    If name_filter is provided, results are fuzzy-matched and limited to top 5.
    """
    start = time.perf_counter()
    logger.info(
        f"Query goals: name_filter={request.name_filter!r}, status={request.status}, "
        f"priority={request.priority}, include_done={request.include_done}"
    )
    try:
        filter_ = _build_goal_filter(request)
        # Default sort by last edited time descending (latest first)
        sorts = [{"timestamp": "last_edited_time", "direction": "descending"}]
        pages_data = client.query_all_data_source(data_source_id, filter_=filter_, sorts=sorts)

        # Parse all pages to goal responses
        goals = [_goal_to_response(parse_page_to_goal(page)) for page in pages_data]

        # Apply fuzzy name filter if provided
        filtered_goals, fuzzy_quality = filter_by_fuzzy_name(
            items=goals,
            name_filter=request.name_filter,
            name_getter=lambda g: g.goal_name,
            limit=request.limit if not request.name_filter else 5,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Query goals complete: found={len(pages_data)}, "
            f"returned={len(filtered_goals)}, elapsed={elapsed_ms:.0f}ms"
        )

        return GoalQueryResponse(
            results=filtered_goals,
            fuzzy_match_quality=fuzzy_quality,
            excluded_done=not request.include_done,
        )
    except NotionClientError as e:
        logger.exception(
            f"Failed to query goals: name_filter={request.name_filter!r}, "
            f"status={request.status}, error={e}"
        )
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
    start = time.perf_counter()
    logger.info(f"Get goal: id={goal_id}")
    try:
        data = client.get_page(goal_id)
        goal = parse_page_to_goal(data)

        # Fetch page content
        blocks = client.get_page_content(goal_id)
        content = blocks_to_markdown(blocks) if blocks else None

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Get goal complete: id={goal_id}, name={goal.goal_name!r}, "
            f"has_content={content is not None}, elapsed={elapsed_ms:.0f}ms"
        )

        return _goal_to_response(goal, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to get goal: id={goal_id}, error={e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=GoalBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create goals",
)
def create_goals(
    requests: list[GoalCreateRequest],
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_goals_data_source_id),
) -> GoalBulkCreateResponse:
    """Create one or more goals in the goals tracker.

    Processes all items and returns both successes and failures.
    Partial success is possible - some items may be created while others fail.
    """
    start = time.perf_counter()
    logger.info(f"Create goals: count={len(requests)}")
    created: list[GoalResponse] = []
    failed: list[BulkCreateFailure] = []

    for i, request in enumerate(requests):
        try:
            check_duplicate_name(
                client=client,
                data_source_id=data_source_id,
                name_property="Goal name",
                complete_status="Done",
                new_name=request.goal_name,
            )

            properties = build_goal_properties(
                goal_name=request.goal_name,
                status=request.status,
                priority=request.priority,
                category=request.category,
                progress=request.progress,
                due_date=request.due_date,
            )
            data = client.create_page(
                data_source_id=data_source_id,
                properties=properties,
            )
            goal = parse_page_to_goal(data)

            # Append content if provided
            if request.content:
                blocks = markdown_to_blocks(request.content)
                client.append_page_content(goal.id, blocks)

            created.append(_goal_to_response(goal, content=request.content))
            logger.debug(f"Create goals [{i + 1}/{len(requests)}]: created id={goal.id}")
        except (NotionClientError, HTTPException) as e:
            error_msg = e.detail if isinstance(e, HTTPException) else str(e)
            logger.warning(
                f"Create goals [{i + 1}/{len(requests)}]: "
                f"failed name={request.goal_name!r}, error={error_msg}"
            )
            failed.append(BulkCreateFailure(name=request.goal_name, error=error_msg))

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Create goals complete: succeeded={len(created)}, "
        f"failed={len(failed)}, elapsed={elapsed_ms:.0f}ms"
    )

    return GoalBulkCreateResponse(created=created, failed=failed)


@router.patch(
    "/{goal_id}",
    response_model=GoalResponse,
    summary="Update goal",
)
def update_goal(
    goal_id: str,
    request: GoalUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_goals_data_source_id),
) -> GoalResponse:
    """Update a goal's properties."""
    start = time.perf_counter()
    fields = list(request.model_dump(exclude_unset=True).keys())
    logger.info(f"Update goal: id={goal_id}, fields={fields}")

    if request.goal_name is not None:
        check_duplicate_name(
            client=client,
            data_source_id=data_source_id,
            name_property="Goal name",
            complete_status="Done",
            new_name=request.goal_name,
            exclude_id=goal_id,
        )

    try:
        properties = build_goal_properties(
            goal_name=request.goal_name,
            status=request.status,
            priority=request.priority,
            category=request.category,
            progress=request.progress,
            due_date=request.due_date,
        )

        if not properties and request.content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties or content to update.",
            )

        # Update properties if any
        if properties:
            data = client.update_page(page_id=goal_id, properties=properties)
            goal = parse_page_to_goal(data)
        else:
            # Content-only update - fetch current goal
            data = client.get_page(goal_id)
            goal = parse_page_to_goal(data)

        # Replace content if provided
        content: str | None
        if request.content is not None:
            new_blocks = markdown_to_blocks(request.content)
            client.replace_page_content(goal_id, new_blocks)
            content = request.content
        else:
            # Fetch existing content
            blocks = client.get_page_content(goal_id)
            content = blocks_to_markdown(blocks) if blocks else None

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Update goal complete: id={goal_id}, name={goal.goal_name!r}, "
            f"elapsed={elapsed_ms:.0f}ms"
        )

        return _goal_to_response(goal, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to update goal: id={goal_id}, fields={fields}, error={e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _build_goal_filter(request: GoalQueryRequest) -> dict[str, object] | None:
    """Build Notion filter from structured query request.

    :param request: Query request with filter fields.
    :returns: Notion filter dictionary or None if no filters.
    """
    conditions: list[dict[str, object]] = []

    # Exclude Done goals by default unless include_done is True
    if not request.include_done:
        conditions.append(
            {"property": "Status", "status": {"does_not_equal": GoalStatus.DONE.value}}
        )

    if request.status:
        conditions.append({"property": "Status", "status": {"equals": request.status.value}})

    if request.priority:
        conditions.append({"property": "Priority", "select": {"equals": request.priority.value}})

    if request.category:
        conditions.append({"property": "Category", "select": {"equals": request.category.value}})

    if request.due_before:
        conditions.append(
            {"property": "Due date", "date": {"before": request.due_before.isoformat()}}
        )

    if request.due_after:
        conditions.append(
            {"property": "Due date", "date": {"after": request.due_after.isoformat()}}
        )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def _goal_to_response(goal: NotionGoal, content: str | None = None) -> GoalResponse:
    """Convert a NotionGoal to a GoalResponse.

    :param goal: The NotionGoal to convert.
    :param content: Optional markdown content for the page.
    :returns: GoalResponse with all fields.
    """
    return GoalResponse(
        id=goal.id,
        goal_name=goal.goal_name,
        status=goal.status,
        priority=goal.priority,
        category=goal.category,
        progress=goal.progress,
        due_date=goal.due_date,
        content=content,
    )
