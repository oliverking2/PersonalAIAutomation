"""Unified alert system for sending proactive Telegram notifications."""

from src.alerts.enums import AlertType
from src.alerts.formatters import (
    format_alert,
    format_bin_schedule_alert,
    format_goal_alert,
    format_medium_alert,
    format_newsletter_alert,
    format_reading_alert,
    format_substack_alert,
    format_task_alert,
)
from src.alerts.models import AlertData, AlertItem, AlertSendResult
from src.alerts.providers import (
    AlertProvider,
    BinScheduleAlertProvider,
    BinType,
    GoalAlertProvider,
    MediumAlertProvider,
    NewsletterAlertProvider,
    OverdueTaskAlertProvider,
    PersonalTaskAlertProvider,
    ReadingAlertProvider,
    SubstackAlertProvider,
    WorkTaskAlertProvider,
)
from src.alerts.service import AlertService

__all__ = [
    "AlertData",
    "AlertItem",
    "AlertProvider",
    "AlertSendResult",
    "AlertService",
    "AlertType",
    "BinScheduleAlertProvider",
    "BinType",
    "GoalAlertProvider",
    "MediumAlertProvider",
    "NewsletterAlertProvider",
    "OverdueTaskAlertProvider",
    "PersonalTaskAlertProvider",
    "ReadingAlertProvider",
    "SubstackAlertProvider",
    "WorkTaskAlertProvider",
    "format_alert",
    "format_bin_schedule_alert",
    "format_goal_alert",
    "format_medium_alert",
    "format_newsletter_alert",
    "format_reading_alert",
    "format_substack_alert",
    "format_task_alert",
]
