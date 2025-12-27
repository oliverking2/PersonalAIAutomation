"""Alert providers package."""

from src.alerts.providers.base import AlertProvider
from src.alerts.providers.goals import GoalAlertProvider
from src.alerts.providers.newsletter import NewsletterAlertProvider
from src.alerts.providers.reading import ReadingAlertProvider
from src.alerts.providers.tasks import TaskAlertProvider

__all__ = [
    "AlertProvider",
    "GoalAlertProvider",
    "NewsletterAlertProvider",
    "ReadingAlertProvider",
    "TaskAlertProvider",
]
