"""Dagster Util Sensors."""

import os

from dagster import (
    DefaultSensorStatus,
    Definitions,
    RunFailureSensorContext,
    run_failure_sensor,
)
from src.telegram import TelegramClient
from src.telegram.utils.misc import _escape_md


@run_failure_sensor(
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=60,
)
def telegram_on_run_failure(context: RunFailureSensorContext) -> None:
    """Send a Telegram alert once per failed run."""
    run = context.dagster_run

    subject = f"Dagster failure: {run.job_name}"

    # Keep it simple and readable in Telegram.
    client = TelegramClient(
        bot_token=os.environ["TELEGRAM_ERROR_BOT_TOKEN"], chat_id=os.environ["TELEGRAM_CHAT_ID"]
    )
    context.log.info(f"Sending Telegram alert for failed run: {subject}")
    text = (
        f"*{_escape_md(subject)}*\n"
        f"Pipeline: `{_escape_md(run.job_name)}`\n"
        f"Run ID: `{_escape_md(run.run_id)}`\n"
    )
    context.log.info(f"Message: {text}")

    client.send_message(text, parse_mode="MarkdownV2")


util_sensor_defs = Definitions(
    sensors=[telegram_on_run_failure],
)
