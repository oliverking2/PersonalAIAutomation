"""Dagster Util Sensors."""

from dagster import (
    DefaultSensorStatus,
    Definitions,
    RunFailureSensorContext,
    run_failure_sensor,
)
from src.telegram import TelegramClient
from src.telegram.utils.config import get_telegram_settings
from src.telegram.utils.misc import _escape_md


@run_failure_sensor(
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=60,
)
def telegram_on_run_failure(context: RunFailureSensorContext) -> None:
    """Send a Telegram alert once per failed run."""
    run = context.dagster_run

    subject = f"Dagster failure: {run.job_name}"

    settings = get_telegram_settings()
    if not settings.error_bot_token or not settings.error_chat_id:
        context.log.warning(
            "Error notification skipped: TELEGRAM_ERROR_BOT_TOKEN or "
            "TELEGRAM_ERROR_CHAT_ID not configured"
        )
        return

    client = TelegramClient(
        bot_token=settings.error_bot_token,
        chat_id=settings.error_chat_id,
    )
    context.log.info(f"Sending Telegram alert for failed run: {subject}")
    text = (
        f"*{_escape_md(subject)}*\n"
        f"Pipeline: `{_escape_md(run.job_name)}`\n"
        f"Run ID: `{_escape_md(run.run_id)}`\n"
    )
    context.log.info(f"Message: {text}")

    client.send_message_sync(text, parse_mode="MarkdownV2")


util_sensor_defs = Definitions(
    sensors=[telegram_on_run_failure],
)
