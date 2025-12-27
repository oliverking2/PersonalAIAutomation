"""Dagster schedules for sending alerts."""

from dagster import ScheduleDefinition
from src.dagster.alerts.jobs import (
    daily_task_alerts_job,
    monthly_goal_alerts_job,
    weekly_reading_alerts_job,
)

# Daily task alerts: 8:00 AM Europe/London
daily_task_alert_schedule = ScheduleDefinition(
    job=daily_task_alerts_job,
    cron_schedule="0 8 * * *",
    execution_timezone="Europe/London",
)

# Monthly goal alerts: 1st Monday of month at 8:00 PM Europe/London
monthly_goal_alert_schedule = ScheduleDefinition(
    job=monthly_goal_alerts_job,
    cron_schedule="0 20 * * 1#1",
    execution_timezone="Europe/London",
)

# Weekly reading alerts: Sunday at 6:00 PM Europe/London
weekly_reading_alert_schedule = ScheduleDefinition(
    job=weekly_reading_alerts_job,
    cron_schedule="0 18 * * 0",
    execution_timezone="Europe/London",
)
