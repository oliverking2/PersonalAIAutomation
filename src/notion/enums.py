"""Enums for Notion task field values."""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Valid status values for tasks."""

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


class GoalStatus(StrEnum):
    """Valid status values for goals."""

    NOT_STARTED = "Not started"
    IN_PROGRESS = "In progress"
    DONE = "Done"


class ReadingStatus(StrEnum):
    """Valid status values for reading list items."""

    TO_READ = "To Read"
    READING_NOW = "Reading Now"
    COMPLETED = "Completed"


class ReadingCategory(StrEnum):
    """Valid category values for reading list items."""

    DATA_ANALYTICS = "Data Analytics"
    DATA_SCIENCE = "Data Science"
    DATA_ENGINEERING = "Data Engineering"
    AI = "AI"


class ReadingType(StrEnum):
    """Valid type values for reading list items."""

    BOOK = "Book"
    ARTICLE = "Article"
    OTHER = "Other"


class IdeaGroup(StrEnum):
    """Valid group values for ideas."""

    WORK = "Work"
    PERSONAL = "Personal"


class IdeaStatus(StrEnum):
    """Valid status values for ideas."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    ARCHIVED = "Archived"
    DONE = "Done"
