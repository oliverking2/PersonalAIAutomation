"""Database package for alert tracking."""

from src.database.alerts.models import AlertType, SentAlert
from src.database.alerts.operations import (
    create_sent_alert,
    get_recent_alerts,
    get_sent_alerts_by_type,
    was_alert_sent_today,
)

__all__ = [
    "AlertType",
    "SentAlert",
    "create_sent_alert",
    "get_recent_alerts",
    "get_sent_alerts_by_type",
    "was_alert_sent_today",
]
