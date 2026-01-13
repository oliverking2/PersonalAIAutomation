"""Tool handlers for the AI agent."""

from src.agent.tools.factory import CRUDToolConfig, create_crud_tools
from src.agent.tools.goals import get_goals_tools
from src.agent.tools.ideas import get_ideas_tools
from src.agent.tools.memory import get_memory_tools
from src.agent.tools.projects import get_projects_tools
from src.agent.tools.reading_list import get_reading_list_tools
from src.agent.tools.reminders import get_reminders_tools
from src.agent.tools.tasks import get_tasks_tools

__all__ = [
    "CRUDToolConfig",
    "create_crud_tools",
    "get_goals_tools",
    "get_ideas_tools",
    "get_memory_tools",
    "get_projects_tools",
    "get_reading_list_tools",
    "get_reminders_tools",
    "get_tasks_tools",
]
