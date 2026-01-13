"""Agent-specific models for tool arguments.

These models differ from API models by using structured inputs
(description, notes) instead of raw content. The tool handlers
transform these inputs into formatted content using templates.
"""

from datetime import date

from pydantic import BaseModel, Field

from src.notion.enums import (
    EffortLevel,
    GoalCategory,
    GoalStatus,
    IdeaGroup,
    IdeaStatus,
    Priority,
    ProjectGroup,
    ProjectPriority,
    ProjectStatus,
    ReadingCategory,
    ReadingStatus,
    ReadingType,
    TaskGroup,
    TaskStatus,
)


class AgentTaskCreateArgs(BaseModel):
    """Agent arguments for creating a task.

    Uses description and notes instead of raw content.
    The tool handler builds formatted content from these fields.
    """

    task_name: str = Field(..., min_length=1, description="Task title")
    description: str | None = Field(
        None,
        description="What needs to be done and why (recommended for complex tasks)",
    )
    notes: str | None = Field(
        None,
        description="Additional context, references, or details",
    )
    due_date: date = Field(..., description="Task due date")
    task_group: TaskGroup = Field(
        ...,
        description=f"Task group category ({', '.join(TaskGroup)})",
    )
    status: TaskStatus | None = Field(
        default=TaskStatus.NOT_STARTED,
        description=f"Task status (default: {TaskStatus.NOT_STARTED})",
    )
    priority: Priority | None = Field(
        default=Priority.LOW,
        description=f"Task priority (default: {Priority.LOW})",
    )
    effort_level: EffortLevel | None = Field(
        default=EffortLevel.SMALL,
        description=f"Task effort level (default: {EffortLevel.SMALL})",
    )
    project_id: str | None = Field(
        None,
        description="Project ID to link this task to (use query_projects to find IDs)",
    )


class AgentGoalCreateArgs(BaseModel):
    """Agent arguments for creating a goal.

    Uses description and notes instead of raw content.
    The tool handler builds formatted content from these fields.
    """

    goal_name: str = Field(..., min_length=1, description="Goal title")
    description: str | None = Field(
        None,
        description="What this goal aims to achieve and why it matters",
    )
    notes: str | None = Field(
        None,
        description="Additional context, milestones, or references",
    )
    status: GoalStatus | None = Field(
        default=GoalStatus.NOT_STARTED,
        description=f"Goal status (default: {GoalStatus.NOT_STARTED})",
    )
    priority: Priority | None = Field(
        default=Priority.LOW,
        description=f"Goal priority (default: {Priority.LOW})",
    )
    category: GoalCategory = Field(
        ...,
        description=f"Goal category ({', '.join(GoalCategory)})",
    )
    progress: int | None = Field(
        default=0,
        ge=0,
        le=100,
        description="Progress percentage (0-100, default: 0)",
    )
    due_date: date = Field(..., description="Target completion date")


class AgentReadingItemCreateArgs(BaseModel):
    """Agent arguments for creating a reading list item.

    Uses notes instead of raw content.
    The tool handler builds formatted content from this field.
    """

    title: str = Field(..., min_length=1, description="Title of the item to read")
    item_type: ReadingType = Field(
        ..., description=f"Type of reading item ({', '.join(ReadingType)})"
    )
    notes: str | None = Field(
        None,
        description="Why this was added or initial thoughts",
    )
    item_url: str | None = Field(None, description="URL of the article, book, or resource to read")
    status: ReadingStatus | None = Field(
        default=ReadingStatus.TO_READ,
        description=f"Reading status (default: {ReadingStatus.TO_READ})",
    )
    priority: Priority | None = Field(
        default=Priority.LOW,
        description=f"Priority (default: {Priority.LOW})",
    )
    category: ReadingCategory = Field(
        ...,
        description=f"Content category ({', '.join(ReadingCategory)})",
    )


# Update models - all fields optional, uses templates for content


class AgentTaskUpdateArgs(BaseModel):
    """Agent arguments for updating a task.

    Uses content field for raw markdown. Agent must fetch existing content
    via get_task, merge changes, and pass the complete content.
    """

    task_name: str | None = Field(None, min_length=1, description="Task title")
    content: str | None = Field(
        None,
        description="Complete page content in markdown (replaces all existing content)",
    )
    due_date: date | None = Field(None, description="Task due date")
    task_group: TaskGroup | None = Field(
        None,
        description=f"Task group category ({', '.join(TaskGroup)})",
    )
    status: TaskStatus | None = Field(
        None,
        description=f"Task status ({', '.join(TaskStatus)})",
    )
    priority: Priority | None = Field(
        None,
        description=f"Task priority ({', '.join(Priority)})",
    )
    effort_level: EffortLevel | None = Field(
        None,
        description=f"Task effort level ({', '.join(EffortLevel)})",
    )
    project_id: str | None = Field(
        None,
        description="Project ID to link this task to",
    )


class AgentGoalUpdateArgs(BaseModel):
    """Agent arguments for updating a goal.

    Uses content field for raw markdown. Agent must fetch existing content
    via get_goal, merge changes, and pass the complete content.
    """

    goal_name: str | None = Field(None, min_length=1, description="Goal title")
    content: str | None = Field(
        None,
        description="Complete page content in markdown (replaces all existing content)",
    )
    status: GoalStatus | None = Field(
        None,
        description=f"Goal status ({', '.join(GoalStatus)})",
    )
    priority: Priority | None = Field(
        None,
        description=f"Goal priority ({', '.join(Priority)})",
    )
    category: GoalCategory | None = Field(
        None,
        description=f"Goal category ({', '.join(GoalCategory)})",
    )
    progress: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Progress percentage (0-100)",
    )
    due_date: date | None = Field(None, description="Target completion date")


class AgentReadingItemUpdateArgs(BaseModel):
    """Agent arguments for updating a reading list item.

    Uses content field for raw markdown. Agent must fetch existing content
    via get_reading_item, merge changes, and pass the complete content.
    """

    title: str | None = Field(None, min_length=1, description="Title of the item")
    item_type: ReadingType | None = Field(
        None, description=f"Type of reading item ({', '.join(ReadingType)})"
    )
    content: str | None = Field(
        None,
        description="Complete page content in markdown (replaces all existing content)",
    )
    item_url: str | None = Field(None, description="URL of the article, book, or resource to read")
    status: ReadingStatus | None = Field(
        None,
        description=f"Reading status ({', '.join(ReadingStatus)})",
    )
    priority: Priority | None = Field(
        None,
        description=f"Priority ({', '.join(Priority)})",
    )
    category: ReadingCategory | None = Field(
        None,
        description=f"Content category ({', '.join(ReadingCategory)})",
    )


class AgentIdeaCreateArgs(BaseModel):
    """Agent arguments for creating an idea.

    Uses notes instead of raw content.
    The tool handler builds formatted content from this field.
    """

    idea: str = Field(
        ...,
        min_length=1,
        description="Descriptive idea title (should convey the core concept)",
    )
    notes: str = Field(
        ...,
        min_length=1,
        description="Details, context, and elaboration on the idea (required)",
    )
    status: IdeaStatus | None = Field(
        default=IdeaStatus.NOT_STARTED,
        description=f"Idea status (default: {IdeaStatus.NOT_STARTED})",
    )
    idea_group: IdeaGroup = Field(
        ...,
        description=f"Idea group ({', '.join(IdeaGroup)})",
    )


class AgentIdeaUpdateArgs(BaseModel):
    """Agent arguments for updating an idea.

    Uses content field for raw markdown. Agent must fetch existing content
    via get_idea, merge changes, and pass the complete content.
    """

    idea: str | None = Field(None, min_length=1, description="Idea title or summary")
    content: str | None = Field(
        None,
        description="Complete page content in markdown (replaces all existing content)",
    )
    status: IdeaStatus | None = Field(
        None,
        description=f"Idea status ({', '.join(IdeaStatus)})",
    )
    idea_group: IdeaGroup | None = Field(
        None,
        description=f"Idea group ({', '.join(IdeaGroup)})",
    )


class AgentProjectCreateArgs(BaseModel):
    """Agent arguments for creating a project.

    Uses description and notes instead of raw content.
    The tool handler builds formatted content from these fields.
    """

    project_name: str = Field(..., min_length=1, description="Project title")
    description: str | None = Field(
        None,
        description="Project scope and objectives",
    )
    notes: str | None = Field(
        None,
        description="Additional context, references, or related tasks",
    )
    project_group: ProjectGroup = Field(
        ...,
        description=f"Work or Personal category ({', '.join(ProjectGroup)})",
    )
    status: ProjectStatus | None = Field(
        default=ProjectStatus.NOT_STARTED,
        description=f"Project status (default: {ProjectStatus.NOT_STARTED})",
    )
    priority: ProjectPriority | None = Field(
        default=ProjectPriority.LOW,
        description=f"Project priority (default: {ProjectPriority.LOW})",
    )


class AgentProjectUpdateArgs(BaseModel):
    """Agent arguments for updating a project.

    Uses content field for raw markdown. Agent must fetch existing content
    via get_project, merge changes, and pass the complete content.
    """

    project_name: str | None = Field(None, min_length=1, description="Project title")
    content: str | None = Field(
        None,
        description="Complete page content in markdown (replaces all existing content)",
    )
    status: ProjectStatus | None = Field(
        None,
        description=f"Project status ({', '.join(ProjectStatus)})",
    )
    priority: ProjectPriority | None = Field(
        None,
        description=f"Project priority ({', '.join(ProjectPriority)})",
    )
    project_group: ProjectGroup | None = Field(
        None,
        description=f"Work or Personal category ({', '.join(ProjectGroup)})",
    )
