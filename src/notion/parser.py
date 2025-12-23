"""Parser functions for Notion API responses.

This module handles the conversion between raw Notion API responses
and the Pydantic models used by the application.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from src.notion.models import NotionTask, TaskFilter


class FieldType(StrEnum):
    """Notion property types for building API payloads."""

    TITLE = "title"
    STATUS = "status"
    DATE = "date"
    SELECT = "select"
    RICH_TEXT = "rich_text"


@dataclass(frozen=True)
class TaskField:
    """Metadata for a task field mapping to Notion properties."""

    notion_name: str
    field_type: FieldType


# Field registry - add new fields here
TASK_FIELDS: dict[str, TaskField] = {
    "task_name": TaskField("Task name", FieldType.TITLE),
    "status": TaskField("Status", FieldType.STATUS),
    "due_date": TaskField("Due date", FieldType.DATE),
    "priority": TaskField("Priority", FieldType.SELECT),
    "effort_level": TaskField("Effort level", FieldType.SELECT),
    "task_group": TaskField("Task Group", FieldType.SELECT),
    "description": TaskField("Description", FieldType.RICH_TEXT),
}


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
        effort_level=_extract_select(properties.get("Effort level", {})),
        task_group=_extract_select(properties.get("Task Group", {})),
        description=_extract_rich_text(properties.get("Description", {})),
        assignee=_extract_people(properties.get("Assignee", {})),
        url=page.get("url", ""),
    )


def _extract_title(prop: dict[str, Any]) -> str:
    """Extract plain text from a title property."""
    title_items = prop.get("title", [])
    return "".join(item.get("plain_text", "") for item in title_items)


def _extract_status(prop: dict[str, Any]) -> str | None:
    """Extract status name from a status property."""
    status = prop.get("status")
    if status is None:
        return None
    return status.get("name")


def _extract_date(prop: dict[str, Any]) -> date | None:
    """Extract date from a date property."""
    date_obj = prop.get("date")
    if date_obj is None:
        return None
    start = date_obj.get("start")
    if start is None:
        return None
    return date.fromisoformat(start)


def _extract_select(prop: dict[str, Any]) -> str | None:
    """Extract selected value from a select property."""
    select = prop.get("select")
    if select is None:
        return None
    return select.get("name")


def _extract_rich_text(prop: dict[str, Any]) -> str | None:
    """Extract plain text from a rich_text property."""
    rich_text_items = prop.get("rich_text", [])
    if not rich_text_items:
        return None
    text = "".join(item.get("plain_text", "") for item in rich_text_items)
    return text if text else None


def _extract_people(prop: dict[str, Any]) -> str | None:
    """Extract first person's name from a people property."""
    people = prop.get("people", [])
    if not people:
        return None
    first_person = people[0]
    return first_person.get("name")


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


def _build_property(field: TaskField, value: Any) -> dict[str, Any]:
    """Build a single Notion property payload."""
    match field.field_type:
        case FieldType.TITLE:
            return {field.notion_name: {"title": [{"text": {"content": value}}]}}
        case FieldType.STATUS:
            return {field.notion_name: {"status": {"name": value}}}
        case FieldType.DATE:
            if value is None:
                return {field.notion_name: {"date": None}}
            return {field.notion_name: {"date": {"start": value.isoformat()}}}
        case FieldType.SELECT:
            return {field.notion_name: {"select": {"name": value}}}
        case FieldType.RICH_TEXT:
            return {field.notion_name: {"rich_text": [{"text": {"content": value}}]}}


def build_task_properties(**kwargs: Any) -> dict[str, Any]:
    """Build properties payload from keyword arguments.

    Only includes properties that are explicitly set (not None).
    Adding a new field requires only adding it to TASK_FIELDS.

    :param kwargs: Field name to value mappings.
    :returns: Combined properties object for the Notion API.
    :raises ValueError: If an unknown field name is provided.
    """
    properties: dict[str, Any] = {}

    for field_name, value in kwargs.items():
        if value is None:
            continue

        if field_name not in TASK_FIELDS:
            raise ValueError(f"Unknown field: {field_name}")

        field = TASK_FIELDS[field_name]
        properties.update(_build_property(field, value))

    return properties
