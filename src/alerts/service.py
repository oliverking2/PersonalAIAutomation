"""Alert service for sending and tracking alerts."""

import logging

from sqlalchemy.orm import Session

from src.alerts.enums import AlertType
from src.alerts.formatters import format_alert
from src.alerts.models import AlertData, AlertSendResult
from src.alerts.providers.base import AlertProvider
from src.database.alerts import create_sent_alert, was_alert_sent_today
from src.telegram.client import TelegramClient, TelegramClientError

logger = logging.getLogger(__name__)


class AlertService:
    """Service for sending alerts via Telegram and tracking them in the database."""

    def __init__(
        self,
        session: Session,
        telegram_client: TelegramClient,
        providers: list[AlertProvider],
    ) -> None:
        """Initialise the alert service.

        :param session: Database session for tracking sent alerts.
        :param telegram_client: Telegram client for sending messages.
        :param providers: List of alert providers to use.
        """
        self._session = session
        self._telegram = telegram_client
        self._providers = providers
        self._provider_map = {p.alert_type: p for p in providers}

    def send_alerts(
        self,
        alert_types: list[AlertType] | None = None,
    ) -> AlertSendResult:
        """Send pending alerts for specified types.

        :param alert_types: Types of alerts to send. If None, sends all types.
        :returns: Result with counts of sent/skipped alerts and any errors.
        """
        result = AlertSendResult()

        for provider in self._providers:
            if alert_types and provider.alert_type not in alert_types:
                continue

            logger.info(f"Processing {provider.alert_type.value} alerts")

            try:
                pending = provider.get_pending_alerts()
            except Exception as e:
                error_msg = f"Failed to get pending {provider.alert_type.value} alerts: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)
                continue

            for alert in pending:
                if self._already_sent_today(alert):
                    logger.debug(f"Skipping already sent alert: {alert.source_id}")
                    result.alerts_skipped += 1
                    continue

                try:
                    self._send_and_track_alert(alert, provider)
                    # Commit after each successful alert to preserve progress
                    # if a later alert fails
                    self._session.commit()
                    result.alerts_sent += 1
                except TelegramClientError as e:
                    error_msg = f"Failed to send {alert.alert_type.value} alert: {e}"
                    logger.exception(error_msg)
                    result.errors.append(error_msg)

        logger.info(
            f"Alert processing complete: "
            f"{result.alerts_sent} sent, {result.alerts_skipped} skipped, "
            f"{len(result.errors)} errors"
        )

        return result

    def _send_and_track_alert(
        self,
        alert: AlertData,
        provider: AlertProvider,
    ) -> None:
        """Send a single alert and track it in the database.

        :param alert: The alert to send.
        :param provider: The provider that generated the alert.
        :raises TelegramClientError: If sending fails.
        """
        content = format_alert(alert)
        send_result = self._telegram.send_message_sync(content)

        # Record in sent_alerts table
        create_sent_alert(
            self._session,
            alert_type=alert.alert_type,
            chat_id=str(send_result.chat_id),
            content=content,
            telegram_message_id=send_result.message_id,
            source_id=alert.source_id,
        )

        # Let the provider do any additional marking
        provider.mark_sent(alert.source_id)

        logger.info(f"Sent {alert.alert_type.value} alert: {alert.source_id}")

    def _already_sent_today(self, alert: AlertData) -> bool:
        """Check if an alert was already sent today.

        :param alert: The alert to check.
        :returns: True if already sent today.
        """
        return was_alert_sent_today(
            self._session,
            alert.alert_type,
            alert.source_id,
        )
