"""Dagster definitions for alert jobs and schedules."""

from dagster import Definitions

from src.orchestration.alerts.jobs import (
    overdue_task_alerts_job,
    personal_task_alerts_job,
    weekly_goal_alerts_job,
    weekly_reading_alerts_job,
    work_task_alerts_job,
)
from src.orchestration.alerts.schedules import (
    overdue_task_alert_schedule,
    personal_task_alert_weekday_schedule,
    personal_task_alert_weekend_schedule,
    weekly_goal_alert_schedule,
    weekly_reading_alert_schedule,
    work_task_alert_schedule,
)

defs = Definitions(
    jobs=[
        work_task_alerts_job,
        personal_task_alerts_job,
        overdue_task_alerts_job,
        weekly_goal_alerts_job,
        weekly_reading_alerts_job,
    ],
    schedules=[
        work_task_alert_schedule,
        personal_task_alert_weekday_schedule,
        personal_task_alert_weekend_schedule,
        overdue_task_alert_schedule,
        weekly_goal_alert_schedule,
        weekly_reading_alert_schedule,
    ],
)
