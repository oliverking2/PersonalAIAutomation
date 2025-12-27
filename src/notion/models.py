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


class NotionGoal(BaseModel):
    """A goal from Notion with parsed properties.

    Represents a page from the goals tracker data source
    with goal-specific properties extracted and normalised.
    """

    id: str = Field(..., min_length=1, description="Notion page ID")
    goal_name: str = Field(..., min_length=1, description="Goal title")
    status: str | None = Field(None, description="Goal status")
    priority: str | None = Field(None, description="Goal priority level")
    category: str | None = Field(None, description="Goal category")
    progress: float | None = Field(None, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")


class NotionReadingItem(BaseModel):
    """A reading list item from Notion with parsed properties.

    Represents a page from the reading list data source
    with reading-specific properties extracted and normalised.
    """

    id: str = Field(..., min_length=1, description="Notion page ID")
    title: str = Field(..., min_length=1, description="Reading item title")
    item_type: str = Field(..., description="Type of reading item (Book, Article, Other)")
    status: str | None = Field(None, description="Reading status")
    priority: str | None = Field(None, description="Reading priority level")
    category: str | None = Field(None, description="Reading category")
    item_url: str | None = Field(None, description="URL of the article/book")


class NotionIdea(BaseModel):
    """An idea from Notion with parsed properties.

    Represents a page from the ideas data source
    with idea-specific properties extracted and normalised.
    """

    id: str = Field(..., min_length=1, description="Notion page ID")
    idea: str = Field(..., min_length=1, description="Idea title")
    status: str | None = Field(None, description="Idea status")
    idea_group: str | None = Field(None, description="Idea group (Work/Personal)")
