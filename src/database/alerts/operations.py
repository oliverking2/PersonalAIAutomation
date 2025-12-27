"""Database operations for alert tracking."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.database.alerts.models import AlertType, SentAlert

logger = logging.getLogger(__name__)


def create_sent_alert(  # noqa: PLR0913
    session: Session,
    alert_type: AlertType,
    chat_id: str,
    content: str,
    telegram_message_id: int | None = None,
    source_id: str | None = None,
) -> SentAlert:
    """Record a sent alert in the database.

    :param session: Database session.
    :param alert_type: Type of alert sent.
    :param chat_id: Telegram chat ID the alert was sent to.
    :param content: Full message content.
    :param telegram_message_id: Telegram's message ID if available.
    :param source_id: Optional reference to source record (e.g., newsletter UUID).
    :returns: The created SentAlert record.
    """
    alert = SentAlert(
        alert_type=alert_type,
        chat_id=chat_id,
        content=content,
        telegram_message_id=telegram_message_id,
        source_id=source_id,
    )
    session.add(alert)
    session.flush()
    logger.info(f"Created sent alert: type={alert_type}, source_id={source_id}")
    return alert


def was_alert_sent_today(
    session: Session,
    alert_type: AlertType,
    source_id: str,
) -> bool:
    """Check if an alert for this source was already sent today.

    Used to prevent duplicate alerts for the same source within a day.

    :param session: Database session.
    :param alert_type: Type of alert to check.
    :param source_id: Source identifier to check.
    :returns: True if an alert was already sent today, False otherwise.
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        session.query(SentAlert)
        .filter(
            SentAlert.alert_type == alert_type,
            SentAlert.source_id == source_id,
            SentAlert.sent_at >= today_start,
        )
        .first()
        is not None
    )


def get_sent_alerts_by_type(
    session: Session,
    alert_type: AlertType,
    since: datetime | None = None,
    limit: int = 100,
) -> list[SentAlert]:
    """Get sent alerts of a specific type.

    :param session: Database session.
    :param alert_type: Type of alerts to retrieve.
    :param since: Optional datetime to filter alerts sent after.
    :param limit: Maximum number of alerts to return.
    :returns: List of SentAlert records.
    """
    query = session.query(SentAlert).filter(SentAlert.alert_type == alert_type)

    if since:
        query = query.filter(SentAlert.sent_at >= since)

    return query.order_by(SentAlert.sent_at.desc()).limit(limit).all()


def get_recent_alerts(
    session: Session,
    hours: int = 24,
    limit: int = 100,
) -> list[SentAlert]:
    """Get all sent alerts from the last N hours.

    Useful for debugging and monitoring alert activity.

    :param session: Database session.
    :param hours: Number of hours to look back.
    :param limit: Maximum number of alerts to return.
    :returns: List of SentAlert records.
    """
    since = datetime.now(UTC) - timedelta(hours=hours)
    return (
        session.query(SentAlert)
        .filter(SentAlert.sent_at >= since)
        .order_by(SentAlert.sent_at.desc())
        .limit(limit)
        .all()
    )
