"""Alert providers package."""

from src.alerts.providers.base import AlertProvider
from src.alerts.providers.goals import GoalAlertProvider
from src.alerts.providers.newsletter import NewsletterAlertProvider
from src.alerts.providers.reading import ReadingAlertProvider
from src.alerts.providers.substack import SubstackAlertProvider
from src.alerts.providers.tasks import (
    OverdueTaskAlertProvider,
    PersonalTaskAlertProvider,
    WorkTaskAlertProvider,
)

__all__ = [
    "AlertProvider",
    "GoalAlertProvider",
    "NewsletterAlertProvider",
    "OverdueTaskAlertProvider",
    "PersonalTaskAlertProvider",
    "ReadingAlertProvider",
    "SubstackAlertProvider",
    "WorkTaskAlertProvider",
]
