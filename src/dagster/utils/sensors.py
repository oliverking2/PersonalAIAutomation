"""Dagster Util Sensors."""

import os

from dagster import (
    DagsterRunStatus,
    DefaultSensorStatus,
    Definitions,
    RunFailureSensorContext,
    run_status_sensor,
)


@run_status_sensor(
    run_status=DagsterRunStatus.FAILURE,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=60,
    required_resource_keys={"telegram_errors"},
)
def telegram_on_run_failure(context: RunFailureSensorContext) -> None:
    """Send a Telegram alert once per failed run."""
    run = context.dagster_run

    dagster_ui = os.environ.get("DAGSTER_WEB_URL", "").rstrip("/")
    link = f"{dagster_ui}/runs/{run.run_id}" if dagster_ui else run.run_id

    subject = f"Dagster failure: {run.job_name}"

    # Keep it simple and readable in Telegram.
    text = (
        f"<b>{subject}</b>\n"
        f"Pipeline: <code>{run.job_name}</code>\n"
        f"Run ID: <code>{run.run_id}</code>\n"
        f"Link: {link}"
    )

    context.resources.telegram_errors.send_message(text)


util_sensor_defs = Definitions(
    sensors=[telegram_on_run_failure],
)
