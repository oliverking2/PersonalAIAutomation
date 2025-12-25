"""Tool handlers for the AI agent."""

from src.agent.tools.goals import get_goals_tools
from src.agent.tools.reading_list import get_reading_list_tools
from src.agent.tools.tasks import get_tasks_tools

__all__ = ["get_goals_tools", "get_reading_list_tools", "get_tasks_tools"]
