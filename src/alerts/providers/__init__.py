"""Alert providers package."""

from src.alerts.providers.base import (
    AlertProvider,
    BaseAlertProvider,
    DatabaseAlertProvider,
    articles_to_alert_items,
)
from src.alerts.providers.bin_schedule import BinScheduleAlertProvider, BinType
from src.alerts.providers.goals import GoalAlertProvider
from src.alerts.providers.medium import MediumAlertProvider
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
    "BaseAlertProvider",
    "BinScheduleAlertProvider",
    "BinType",
    "DatabaseAlertProvider",
    "GoalAlertProvider",
    "MediumAlertProvider",
    "NewsletterAlertProvider",
    "OverdueTaskAlertProvider",
    "PersonalTaskAlertProvider",
    "ReadingAlertProvider",
    "SubstackAlertProvider",
    "WorkTaskAlertProvider",
    "articles_to_alert_items",
]
