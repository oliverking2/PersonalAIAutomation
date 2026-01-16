"""Dagster schedules for sending alerts."""

from dagster import ScheduleDefinition

from src.orchestration.alerts.jobs import (
    overdue_task_alerts_job,
    personal_task_alerts_job,
    weekly_goal_alerts_job,
    weekly_reading_alerts_job,
    work_task_alerts_job,
)

# Work task alerts: 9:00 AM Europe/London daily
work_task_alert_schedule = ScheduleDefinition(
    job=work_task_alerts_job,
    cron_schedule="0 9 * * *",
    execution_timezone="Europe/London",
)

# Personal tasks - Weekday alerts: 6:00 PM Mon-Fri
personal_task_alert_weekday_schedule = ScheduleDefinition(
    name="personal_task_alert_weekday_schedule",
    job=personal_task_alerts_job,
    cron_schedule="0 18 * * 1-5",
    execution_timezone="Europe/London",
)

# Personal tasks - Weekend alerts: 8:00 AM Sat-Sun
personal_task_alert_weekend_schedule = ScheduleDefinition(
    name="personal_task_alert_weekend_schedule",
    job=personal_task_alerts_job,
    cron_schedule="0 8 * * 0,6",
    execution_timezone="Europe/London",
)

# Overdue task alerts: 9:00 PM Europe/London daily
overdue_task_alert_schedule = ScheduleDefinition(
    job=overdue_task_alerts_job,
    cron_schedule="0 21 * * *",
    execution_timezone="Europe/London",
)

# Weekly goal alerts: Monday at 7:00 AM Europe/London
weekly_goal_alert_schedule = ScheduleDefinition(
    job=weekly_goal_alerts_job,
    cron_schedule="0 7 * * 1",
    execution_timezone="Europe/London",
)

# Weekly reading alerts: Sunday at 6:00 PM Europe/London
weekly_reading_alert_schedule = ScheduleDefinition(
    job=weekly_reading_alerts_job,
    cron_schedule="0 18 * * 0",
    execution_timezone="Europe/London",
)
