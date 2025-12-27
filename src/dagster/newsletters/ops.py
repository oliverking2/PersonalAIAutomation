"""Dagster ops for newsletter processing and alerting."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dagster import Backoff, Jitter, OpExecutionContext, RetryPolicy, op
from src.alerts import AlertService, AlertType, NewsletterAlertProvider
from src.database.connection import get_session
from src.database.extraction_state import get_watermark, set_watermark
from src.database.newsletters import backfill_article_urls
from src.enums import ExtractionSource
from src.graph.auth import GraphAPI
from src.newsletters.tldr.service import NewsletterService
from src.telegram import TelegramClient
from src.telegram.utils.config import get_telegram_settings

# Email address to fetch newsletters for
GRAPH_USER_EMAIL = os.environ["GRAPH_TARGET_UPN"]

# Retry policy
NEWSLETTER_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    delay=60,  # 1 minute initial delay
    backoff=Backoff.EXPONENTIAL,
    jitter=Jitter.FULL,
)


@dataclass
class AlertStats:
    """Stats for alerting operations."""

    newsletters_sent: int
    errors: list[str]


@dataclass
class NewsletterStats:
    """Stats for newsletter processing operations."""

    newsletters_processed: int
    articles_new: int
    articles_duplicate: int
    urls_backfilled: int


@op(
    name="process_newsletters",
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Fetch and process newsletters from Microsoft Graph API.",
)
def process_newsletters_op(context: OpExecutionContext) -> NewsletterStats:
    """Process newsletters using watermark-based incremental extraction.

    Fetches newsletters from Graph API (since the last watermark or override),
    parses them, stores in database, and updates the watermark.
    Also backfills any missing parsed URLs for articles.

    :param context: Dagster execution context.
    :returns: Dictionary with processing statistics.
    """
    graph_client = GraphAPI(GRAPH_USER_EMAIL)

    with get_session() as session:
        # Determine the since datetime
        since = get_watermark(session, ExtractionSource.NEWSLETTER_TLDR)
        if since is not None:
            context.log.info(f"Using watermark: {since}")
        else:
            # default to 7 days ago if no watermark is found
            since = datetime.now(UTC) - timedelta(days=7)
            context.log.info("No watermark found, processing last 7 days of emails")

        # Process newsletters
        newsletter_service = NewsletterService(session, graph_client)
        result = newsletter_service.process_newsletters(since=since)

        # Update watermark if we processed any newsletters
        if result.latest_received_at is not None:
            set_watermark(session, ExtractionSource.NEWSLETTER_TLDR, result.latest_received_at)
            context.log.info(f"Updated watermark to: {result.latest_received_at}")

        # Backfill any articles missing parsed URLs
        backfill_result = backfill_article_urls(session)

    stats = NewsletterStats(
        newsletters_processed=result.newsletters_processed,
        articles_new=result.articles_new,
        articles_duplicate=result.articles_duplicate,
        urls_backfilled=backfill_result.articles_updated,
    )

    context.log.info(f"Newsletter processing complete: {result}")
    return stats


@op(
    name="send_newsletter_alerts",
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Send Telegram alerts for unsent newsletters.",
)
def send_alerts_op(context: OpExecutionContext, newsletter_stats: NewsletterStats) -> AlertStats:
    """Send Telegram alerts for unsent newsletters.

    Uses the unified AlertService with NewsletterAlertProvider to send
    alerts for newsletters that haven't been alerted yet.

    :param context: Dagster execution context.
    :param newsletter_stats: Stats from previous newsletter processing op.
    :returns: Dictionary with alerting statistics.
    """
    context.log.info(
        f"Starting Telegram alerts (processed {newsletter_stats.newsletters_processed} newsletters)"
    )

    settings = get_telegram_settings()
    telegram_client = TelegramClient(
        bot_token=settings.bot_token,
        chat_id=settings.chat_id,
    )

    with get_session() as session:
        provider = NewsletterAlertProvider(session)
        alert_service = AlertService(
            session=session,
            telegram_client=telegram_client,
            providers=[provider],
        )
        result = alert_service.send_alerts(alert_types=[AlertType.NEWSLETTER])

    stats = AlertStats(
        newsletters_sent=result.alerts_sent,
        errors=result.errors,
    )

    context.log.info(
        f"Telegram alerts complete: {result.alerts_sent} sent, {len(result.errors)} errors"
    )
    return stats
