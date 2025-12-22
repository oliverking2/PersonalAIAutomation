"""Parser functions for Notion API responses.

This module handles the conversion between raw Notion API responses
and the Pydantic models used by the application.
"""

from datetime import date
from typing import Any

from src.notion.models import NotionTask, TaskFilter


def parse_page_to_task(page: dict[str, Any]) -> NotionTask:
    """Parse a Notion page response into a NotionTask model.

    :param page: Raw page object from Notion API response.
    :returns: Parsed NotionTask with extracted properties.
    """
    properties = page.get("properties", {})

    return NotionTask(
        id=page["id"],
        task_name=_extract_title(properties.get("Task name", {})),
        status=_extract_status(properties.get("Status", {})),
        due_date=_extract_date(properties.get("Due date", {})),
        priority=_extract_select(properties.get("Priority", {})),
        work_personal=_extract_select(properties.get("Work/Personal", {})),
        url=page.get("url", ""),
    )


def _extract_title(prop: dict[str, Any]) -> str:
    """Extract plain text from a title property.

    :param prop: Title property object from Notion.
    :returns: Combined plain text from all title segments.
    """
    title_items = prop.get("title", [])
    return "".join(item.get("plain_text", "") for item in title_items)


def _extract_status(prop: dict[str, Any]) -> str | None:
    """Extract status name from a status property.

    :param prop: Status property object from Notion.
    :returns: Status name or None if not set.
    """
    status = prop.get("status")
    if status is None:
        return None
    return status.get("name")


def _extract_date(prop: dict[str, Any]) -> date | None:
    """Extract date from a date property.

    :param prop: Date property object from Notion.
    :returns: Date object or None if not set.
    """
    date_obj = prop.get("date")
    if date_obj is None:
        return None
    start = date_obj.get("start")
    if start is None:
        return None
    return date.fromisoformat(start)


def _extract_select(prop: dict[str, Any]) -> str | None:
    """Extract selected value from a select property.

    :param prop: Select property object from Notion.
    :returns: Selected option name or None if not set.
    """
    select = prop.get("select")
    if select is None:
        return None
    return select.get("name")


def build_query_filter(filter_: TaskFilter) -> dict[str, Any]:
    """Build a Notion API filter from a TaskFilter model.

    :param filter_: Filter criteria to convert.
    :returns: Notion API filter object for the query endpoint.
    """
    conditions: list[dict[str, Any]] = []

    if filter_.has_title:
        conditions.append(
            {
                "property": "Task name",
                "title": {"is_not_empty": True},
            }
        )

    if filter_.status_not_equals is not None:
        conditions.append(
            {
                "property": "Status",
                "status": {"does_not_equal": filter_.status_not_equals},
            }
        )

    if filter_.due_date_before is not None:
        conditions.append(
            {
                "property": "Due date",
                "date": {"before": filter_.due_date_before.isoformat()},
            }
        )

    if not conditions:
        return {}

    if len(conditions) == 1:
        return {"filter": conditions[0]}

    return {"filter": {"and": conditions}}


def build_status_property(status: str) -> dict[str, Any]:
    """Build a Notion status property update payload.

    :param status: Status name to set.
    :returns: Property update object for the Notion API.
    """
    return {
        "Status": {
            "status": {"name": status},
        },
    }


def build_date_property(date_value: date | None) -> dict[str, Any]:
    """Build a Notion date property update payload.

    :param date_value: Date to set, or None to clear.
    :returns: Property update object for the Notion API.
    """
    if date_value is None:
        return {
            "Due date": {
                "date": None,
            },
        }

    return {
        "Due date": {
            "date": {"start": date_value.isoformat()},
        },
    }


def build_title_property(title: str) -> dict[str, Any]:
    """Build a Notion title property payload for page creation.

    :param title: Title text to set.
    :returns: Property object for the Notion API.
    """
    return {
        "Task name": {
            "title": [
                {
                    "text": {"content": title},
                },
            ],
        },
    }


def build_create_properties(
    task_name: str,
    status: str | None = None,
    due_date: date | None = None,
) -> dict[str, Any]:
    """Build properties payload for creating a new page.

    :param task_name: Title for the new task.
    :param status: Optional initial status.
    :param due_date: Optional due date.
    :returns: Combined properties object for the Notion API.
    """
    properties: dict[str, Any] = build_title_property(task_name)

    if status is not None:
        properties.update(build_status_property(status))

    if due_date is not None:
        properties.update(build_date_property(due_date))

    return properties


def build_update_properties(
    status: str | None = None,
    due_date: date | None = None,
) -> dict[str, Any]:
    """Build properties payload for updating a page.

    Only includes properties that are explicitly set.

    :param status: New status value, or None to leave unchanged.
    :param due_date: New due date, or None to leave unchanged.
    :returns: Properties object for the Notion API.
    """
    properties: dict[str, Any] = {}

    if status is not None:
        properties.update(build_status_property(status))

    if due_date is not None:
        properties.update(build_date_property(due_date))

    return properties
