"""Pydantic models for Notion API data."""

from datetime import date

from pydantic import BaseModel, Field


class NotionTask(BaseModel):
    """A task from Notion with parsed properties.

    Represents a page from a Notion data source with task-specific
    properties extracted and normalised.
    """

    id: str = Field(..., min_length=1, description="Notion page ID")
    task_name: str = Field(..., min_length=1, description="Task title")
    status: str | None = Field(None, description="Task status")
    due_date: date | None = Field(None, description="Task due date")
    priority: str | None = Field(None, description="Task priority level")
    effort_level: str | None = Field(None, description="Task effort level")
    task_group: str | None = Field(None, description="Work or Personal category")
    description: str | None = Field(None, description="Task description")
    assignee: str | None = Field(None, description="Assigned user name")
    url: str = Field(..., description="Notion page URL")


class TaskFilter(BaseModel):
    """Filter criteria for querying tasks from Notion.

    Maps to Notion's filter format for the data source query endpoint.
    """

    status_not_equals: str | None = Field(
        None,
        description="Exclude tasks with this status",
    )
    due_date_before: date | None = Field(
        None,
        description="Only tasks due before this date",
    )
    has_title: bool = Field(
        default=True,
        description="Only tasks with a non-empty title",
    )


class QueryResult(BaseModel):
    """Result from querying a Notion data source.

    Contains the list of tasks and pagination information.
    """

    tasks: list[NotionTask] = Field(default_factory=list)
    has_more: bool = Field(default=False)
    next_cursor: str | None = Field(None)
