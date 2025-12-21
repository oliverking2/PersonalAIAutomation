"""Celery pipelines and schedules."""

from typing import Any

from celery import Celery, chain
from celery.canvas import Signature
from celery.schedules import crontab

from src.orchestration.celery_app import celery_app
from src.orchestration.tasks import process_newsletters_task, send_alerts_task


# Define pipelines for both FastAPI and for Beat
def newsletter_pipeline(*, days_back: int = 1) -> Signature:
    """Build the newsletter pipeline workflow.

    :returns: A Celery chain of tasks.
    """
    return chain(
        process_newsletters_task.s(days_back=days_back),
        send_alerts_task.s(),
    )


# Beat schedule for periodic tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs: Any) -> None:
    """Set up periodic tasks."""
    sender.add_periodic_task(
        crontab(minute=0),
        chain(
            process_newsletters_task.s(),
            send_alerts_task.s(),
        ),
        name="process-then-alert",
    )
