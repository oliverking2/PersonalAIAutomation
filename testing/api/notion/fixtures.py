"""Shared test fixtures for Notion API tests.

These fixtures use actual enum values from the codebase, so tests don't break
when enum values are added, removed, or renamed in Notion.
"""

from typing import Any

from src.notion.enums import (
    EffortLevel,
    GoalStatus,
    IdeaGroup,
    IdeaStatus,
    Priority,
    ReadingCategory,
    ReadingStatus,
    ReadingType,
    TaskGroup,
    TaskStatus,
)


def first_value(enum_class: type) -> str:
    """Get the first value from an enum class.

    :param enum_class: The StrEnum class.
    :returns: The first enum member's value.
    """
    return next(iter(enum_class)).value


# Default enum values for tests - uses first value of each enum
DEFAULT_TASK_STATUS = first_value(TaskStatus)
DEFAULT_PRIORITY = first_value(Priority)
DEFAULT_EFFORT = first_value(EffortLevel)
DEFAULT_TASK_GROUP = first_value(TaskGroup)
DEFAULT_GOAL_STATUS = first_value(GoalStatus)
DEFAULT_READING_STATUS = first_value(ReadingStatus)
DEFAULT_READING_TYPE = first_value(ReadingType)
DEFAULT_READING_CATEGORY = first_value(ReadingCategory)
DEFAULT_IDEA_STATUS = first_value(IdeaStatus)
DEFAULT_IDEA_GROUP = first_value(IdeaGroup)


def build_notion_task_properties(  # noqa: PLR0913
    task_name: str = "Test Task",
    status: str | None = None,
    due_date: str | None = "2025-12-31",
    priority: str | None = None,
    effort_level: str | None = None,
    task_group: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build mock Notion task properties using actual enum values.

    :param task_name: Task title.
    :param status: Task status (defaults to first TaskStatus value).
    :param due_date: Due date string.
    :param priority: Priority (defaults to first Priority value).
    :param effort_level: Effort level (defaults to first EffortLevel value).
    :param task_group: Task group (defaults to first TaskGroup value).
    :param description: Optional description.
    :returns: Mock Notion properties dict.
    """
    return {
        "Task name": {"title": [{"plain_text": task_name}]},
        "Status": {"status": {"name": status or DEFAULT_TASK_STATUS}},
        "Due date": {"date": {"start": due_date} if due_date else None},
        "Priority": {"select": {"name": priority or DEFAULT_PRIORITY}},
        "Effort level": {"select": {"name": effort_level or DEFAULT_EFFORT}},
        "Task Group": {"select": {"name": task_group or DEFAULT_TASK_GROUP}},
        "Description": {"rich_text": [{"plain_text": description}] if description else []},
        "Assignee": {"people": []},
    }


def build_notion_task_page(
    page_id: str = "task-123",
    url: str = "https://notion.so/Task",
    **properties_kwargs: Any,
) -> dict[str, Any]:
    """Build a complete mock Notion task page.

    :param page_id: The page ID.
    :param url: The Notion URL.
    :param properties_kwargs: Arguments passed to build_notion_task_properties.
    :returns: Mock Notion page dict.
    """
    return {
        "id": page_id,
        "url": url,
        "properties": build_notion_task_properties(**properties_kwargs),
    }


def build_notion_goal_properties(  # noqa: PLR0913
    goal_name: str = "Test Goal",
    status: str | None = None,
    priority: str | None = None,
    progress: int = 0,
    due_date: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build mock Notion goal properties using actual enum values.

    :param goal_name: Goal title.
    :param status: Goal status (defaults to first GoalStatus value).
    :param priority: Priority (defaults to first Priority value).
    :param progress: Progress percentage (0-100).
    :param due_date: Optional due date string.
    :param description: Optional description.
    :returns: Mock Notion properties dict.
    """
    return {
        "Goal name": {"title": [{"plain_text": goal_name}]},
        "Status": {"status": {"name": status or DEFAULT_GOAL_STATUS}},
        "Priority": {"select": {"name": priority or DEFAULT_PRIORITY}},
        "Progress": {"number": progress},
        "Due date": {"date": {"start": due_date} if due_date else None},
        "Description": {"rich_text": [{"plain_text": description}] if description else []},
    }


def build_notion_goal_page(
    page_id: str = "goal-123",
    url: str = "https://notion.so/Goal",
    **properties_kwargs: Any,
) -> dict[str, Any]:
    """Build a complete mock Notion goal page.

    :param page_id: The page ID.
    :param url: The Notion URL.
    :param properties_kwargs: Arguments passed to build_notion_goal_properties.
    :returns: Mock Notion page dict.
    """
    return {
        "id": page_id,
        "url": url,
        "properties": build_notion_goal_properties(**properties_kwargs),
    }


def build_notion_reading_properties(  # noqa: PLR0913
    title: str = "Test Article",
    item_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = DEFAULT_READING_CATEGORY,
    item_url: str | None = "https://example.com/article",
) -> dict[str, Any]:
    """Build mock Notion reading list properties using actual enum values.

    :param title: Item title.
    :param item_type: Item type (defaults to first ReadingType value).
    :param status: Reading status (defaults to first ReadingStatus value).
    :param priority: Priority (defaults to first Priority value).
    :param category: Reading category (defaults to first ReadingCategory value). Pass None for no category.
    :param item_url: Optional URL.
    :returns: Mock Notion properties dict.
    """
    return {
        "Title": {"title": [{"plain_text": title}]},
        "Type": {"select": {"name": item_type or DEFAULT_READING_TYPE}},
        "Status": {"status": {"name": status or DEFAULT_READING_STATUS}},
        "Priority": {"select": {"name": priority or DEFAULT_PRIORITY}},
        "Category": {"select": {"name": category} if category else None},
        "URL": {"url": item_url},
    }


def build_notion_reading_page(
    page_id: str = "reading-123",
    url: str = "https://notion.so/Reading",
    **properties_kwargs: Any,
) -> dict[str, Any]:
    """Build a complete mock Notion reading list page.

    :param page_id: The page ID.
    :param url: The Notion URL.
    :param properties_kwargs: Arguments passed to build_notion_reading_properties.
    :returns: Mock Notion page dict.
    """
    return {
        "id": page_id,
        "url": url,
        "properties": build_notion_reading_properties(**properties_kwargs),
    }


def build_notion_idea_properties(
    idea: str = "Test Idea",
    status: str | None = None,
    idea_group: str | None = DEFAULT_IDEA_GROUP,
) -> dict[str, Any]:
    """Build mock Notion idea properties using actual enum values.

    :param idea: Idea title.
    :param status: Idea status (defaults to first IdeaStatus value).
    :param idea_group: Idea group (defaults to first IdeaGroup value). Pass None for no group.
    :returns: Mock Notion properties dict.
    """
    return {
        "Idea": {"title": [{"plain_text": idea}]},
        "Status": {"status": {"name": status or DEFAULT_IDEA_STATUS}},
        "Idea Group": {"select": {"name": idea_group} if idea_group else None},
    }


def build_notion_idea_page(
    page_id: str = "idea-123",
    url: str = "https://notion.so/Idea",
    **properties_kwargs: Any,
) -> dict[str, Any]:
    """Build a complete mock Notion idea page.

    :param page_id: The page ID.
    :param url: The Notion URL.
    :param properties_kwargs: Arguments passed to build_notion_idea_properties.
    :returns: Mock Notion page dict.
    """
    return {
        "id": page_id,
        "url": url,
        "properties": build_notion_idea_properties(**properties_kwargs),
    }


# Request payload builders for API calls


def build_task_create_payload(  # noqa: PLR0913
    task_name: str = "New Task",
    due_date: str = "2025-12-31",
    task_group: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    effort_level: str | None = None,
) -> dict[str, Any]:
    """Build a task creation request payload.

    :param task_name: Task title.
    :param due_date: Due date string.
    :param task_group: Task group (defaults to first TaskGroup value).
    :param status: Optional status override.
    :param priority: Optional priority override.
    :param effort_level: Optional effort level override.
    :returns: Request payload dict.
    """
    payload: dict[str, Any] = {
        "task_name": task_name,
        "due_date": due_date,
        "task_group": task_group or DEFAULT_TASK_GROUP,
    }
    if status:
        payload["status"] = status
    if priority:
        payload["priority"] = priority
    if effort_level:
        payload["effort_level"] = effort_level
    return payload


def build_goal_create_payload(
    goal_name: str = "New Goal",
    status: str | None = None,
    priority: str | None = None,
    progress: int | None = None,
) -> dict[str, Any]:
    """Build a goal creation request payload.

    :param goal_name: Goal title.
    :param status: Optional status override.
    :param priority: Optional priority override.
    :param progress: Optional progress value.
    :returns: Request payload dict.
    """
    payload: dict[str, Any] = {"goal_name": goal_name}
    if status:
        payload["status"] = status
    if priority:
        payload["priority"] = priority
    if progress is not None:
        payload["progress"] = progress
    return payload


def build_reading_create_payload(  # noqa: PLR0913
    title: str = "New Article",
    item_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    item_url: str | None = None,
) -> dict[str, Any]:
    """Build a reading item creation request payload.

    :param title: Item title.
    :param item_type: Item type (defaults to first ReadingType value).
    :param status: Optional status override.
    :param priority: Optional priority override.
    :param category: Optional category.
    :param item_url: Optional URL.
    :returns: Request payload dict.
    """
    payload: dict[str, Any] = {
        "title": title,
        "item_type": item_type or DEFAULT_READING_TYPE,
    }
    if status:
        payload["status"] = status
    if priority:
        payload["priority"] = priority
    if category:
        payload["category"] = category
    if item_url:
        payload["item_url"] = item_url
    return payload


def build_idea_create_payload(
    idea: str = "New Idea",
    status: str | None = None,
    idea_group: str | None = None,
) -> dict[str, Any]:
    """Build an idea creation request payload.

    :param idea: Idea title.
    :param status: Optional status override.
    :param idea_group: Optional idea group.
    :returns: Request payload dict.
    """
    payload: dict[str, Any] = {"idea": idea}
    if status:
        payload["status"] = status
    if idea_group:
        payload["idea_group"] = idea_group
    return payload
