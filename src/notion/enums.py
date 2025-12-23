"""Enums for Notion task field values."""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Valid status values for tasks."""

    THOUGHT = "Thought"
    NOT_STARTED = "Not started"
    IN_PROGRESS = "In progress"
    DONE = "Done"


class Priority(StrEnum):
    """Valid priority values for tasks."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class EffortLevel(StrEnum):
    """Valid effort level values for tasks."""

    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"


class TaskGroup(StrEnum):
    """Valid task group category values for tasks."""

    PERSONAL = "Personal"
    WORK = "Work"
    PHOTOGRAPHY = "Photography"
