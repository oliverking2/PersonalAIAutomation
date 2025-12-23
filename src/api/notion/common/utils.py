"""Common utilities for Notion API."""

from src.api.notion.common.models import PageResponse
from src.notion import NotionTask


def _page_to_response(task: NotionTask) -> PageResponse:
    """Convert a NotionTask to a PageResponse."""
    return PageResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        due_date=task.due_date,
        priority=task.priority,
        url=task.url,
    )
