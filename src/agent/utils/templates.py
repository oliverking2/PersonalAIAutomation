"""Content templates for agent-created items.

This module provides template builders for generating structured markdown
content when creating tasks, goals, and reading list items via the agent.
"""

from datetime import date


def build_task_content(
    description: str | None = None,
    notes: str | None = None,
) -> str:
    """Build markdown content for a task page.

    :param description: What needs to be done and why.
    :param notes: Additional context or references.
    :returns: Formatted markdown string.
    """
    lines: list[str] = []
    if description:
        lines.extend(["## Description", description, ""])
    if notes:
        lines.extend(["## Notes", notes, ""])

    lines.extend(["---", f"Created via AI Agent on {date.today()}"])
    return "\n".join(lines)


def build_goal_content(
    description: str | None = None,
    notes: str | None = None,
) -> str:
    """Build markdown content for a goal page.

    :param description: What this goal aims to achieve.
    :param notes: Additional context or references.
    :returns: Formatted markdown string.
    """
    lines: list[str] = []
    if description:
        lines.extend(["## Description", description, ""])
    if notes:
        lines.extend(["## Notes", notes, ""])

    lines.extend(["---", f"Created via AI Agent on {date.today()}"])
    return "\n".join(lines)


def build_reading_item_content(notes: str | None = None) -> str:
    """Build markdown content for a reading list item.

    :param notes: Initial notes about why this item was added.
    :returns: Formatted markdown string.
    """
    lines = ["## Notes"]
    if notes:
        lines.append(notes)
    else:
        lines.append("(Add notes after reading)")

    lines.extend(["", "---", f"Added via AI Agent on {date.today()}"])
    return "\n".join(lines)
