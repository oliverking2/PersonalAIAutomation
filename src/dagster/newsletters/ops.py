"""Dagster ops for newsletter processing and alerting."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from dagster import Backoff, Jitter, OpExecutionContext, RetryPolicy, op
from src.database.connection import get_session
from src.database.newsletters import backfill_article_urls
from src.graph.auth import GraphAPI
from src.newsletters.tldr.service import NewsletterService
from src.telegram import TelegramClient, TelegramService

# Email address to fetch newsletters for
GRAPH_USER_EMAIL = os.environ["GRAPH_TARGET_UPN"]


@dataclass
class AlertStats:
    """Stats for alerting operations."""

    newsletters_sent: int
    errors: list[str]


# Retry policy
NEWSLETTER_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    delay=60,  # 1 minute initial delay
    backoff=Backoff.EXPONENTIAL,
    jitter=Jitter.FULL,
)


@op(
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Fetch and process newsletters from Microsoft Graph API.",
)
def process_newsletters_op(context: OpExecutionContext) -> dict[str, int]:
    """Process newsletters from the past day.

    Fetches newsletters from Graph API, parses them, and stores in database.
    Also backfills any missing parsed URLs for articles.

    :param context: Dagster execution context.
    :returns: Dictionary with processing statistics.
    """
    days_back = 1

    context.log.info(f"Starting newsletter processing (days_back={days_back})")

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

    context.log.info(f"Newsletter processing complete: {stats}")
    return stats


@op(
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Send Telegram alerts for unsent newsletters.",
)
def send_alerts_op(context: OpExecutionContext, newsletter_stats: dict[str, Any]) -> AlertStats:
    """Send Telegram alerts for unsent newsletters.

    Queries for newsletters that haven't been alerted yet and sends
    Telegram messages for each.

    :param context: Dagster execution context.
    :param newsletter_stats: Stats from previous newsletter processing op.
    :returns: Dictionary with alerting statistics.
    """
    context.log.info(
        f"Starting Telegram alerts (processed {newsletter_stats.get('newsletters_processed', 0)} newsletters)"
    )

    telegram_client = TelegramClient()

    with get_session() as session:
        telegram_service = TelegramService(session, telegram_client)
        result = telegram_service.send_unsent_newsletters()

    stats = AlertStats(
        newsletters_sent=result.newsletters_sent,
        errors=result.errors,
    )

    context.log.info(
        f"Telegram alerts complete: {result.newsletters_sent} sent, {len(result.errors)} errors"
    )
    return stats
