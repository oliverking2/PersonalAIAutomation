"""Celery tasks for newsletter processing and alerting."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import Celery, Task, chain
from celery.schedules import crontab
from dotenv import load_dotenv

from src.database.connection import get_session
from src.database.newsletters import backfill_article_urls
from src.graph.auth import GraphAPI
from src.newsletters.tldr.service import NewsletterService
from src.orchestration.celery_app import celery_app
from src.telegram import TelegramClient, TelegramService
from src.utils.logging import configure_logging

load_dotenv()
configure_logging()

logger = logging.getLogger(__name__)

# Default retry settings for tasks
DEFAULT_RETRY_KWARGS = {
    "max_retries": 3,
    "default_retry_delay": 60,  # 1 minute
}

# Email address to fetch newsletters for
GRAPH_USER_EMAIL = os.environ["GRAPH_TARGET_UPN"]


class BaseTask(Task):
    """Base task class with common retry and error handling."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="src.orchestration.tasks.process_newsletters_task",
    **DEFAULT_RETRY_KWARGS,
)
def process_newsletters_task(self: Task, *, days_back: int = 1) -> dict[str, int]:
    """Process newsletters from the past N days.

    Fetches newsletters from Graph API, parses them, and stores in database.
    Also backfills any missing parsed URLs for articles.

    :param self: The Celery task instance (bound).
    :param days_back: Number of days to look back for newsletters.
    :returns: Dictionary with processing statistics.
    """
    logger.info(f"Starting newsletter processing task (days_back={days_back})")

    try:
        graph_client = GraphAPI(GRAPH_USER_EMAIL)
        since = datetime.now(UTC) - timedelta(days=days_back)

        with get_session() as session:
            newsletter_service = NewsletterService(session, graph_client)
            result = newsletter_service.process_newsletters(since=since)

            # Backfill any articles missing parsed URLs
            backfill_result = backfill_article_urls(session)

        stats = {
            "newsletters_processed": result.newsletters_processed,
            "articles_new": result.articles_new,
            "articles_duplicate": result.articles_duplicate,
            "urls_backfilled": backfill_result.articles_updated,
        }

        logger.info(f"Newsletter processing complete: {stats}")
        return stats

    except Exception as exc:
        logger.exception(f"Newsletter processing failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="src.orchestration.tasks.send_alerts_task",
    **DEFAULT_RETRY_KWARGS,
)
def send_alerts_task(self: Task) -> dict[str, int | list[str]]:
    """Send Telegram alerts for unsent newsletters.

    Queries for newsletters that haven't been alerted yet and sends
    Telegram messages for each.

    :param self: The Celery task instance (bound).
    :returns: Dictionary with alerting statistics.
    """
    logger.info("Starting Telegram alerts task")

    try:
        telegram_client = TelegramClient()

        with get_session() as session:
            telegram_service = TelegramService(session, telegram_client)
            result = telegram_service.send_unsent_newsletters()

        stats: dict[str, int | list[str]] = {
            "newsletters_sent": result.newsletters_sent,
            "errors": result.errors,
        }

        logger.info(
            f"Telegram alerts complete: {result.newsletters_sent} sent, {len(result.errors)} errors"
        )
        return stats

    except Exception as exc:
        logger.exception(f"Telegram alerts failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="src.orchestration.tasks.run_full_pipeline_task",
    **DEFAULT_RETRY_KWARGS,
)
def run_full_pipeline_task(self: Task, *, days_back: int = 1) -> dict[str, object]:
    """Run the full newsletter pipeline: process then alert.

    Convenience task that runs both processing and alerting in sequence.

    :param self: The Celery task instance (bound).
    :param days_back: Number of days to look back for newsletters.
    :returns: Combined statistics from both operations.
    """
    logger.info(f"Starting full pipeline task (days_back={days_back})")

    process_result = process_newsletters_task(days_back=days_back)
    alert_result = send_alerts_task()

    return {
        "processing": process_result,
        "alerting": alert_result,
    }


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
