"""Dagster ops for newsletter processing and alerting."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dagster import Backoff, Jitter, OpExecutionContext, RetryPolicy, op
from src.alerts import (
    AlertService,
    AlertType,
    MediumAlertProvider,
    NewsletterAlertProvider,
    SubstackAlertProvider,
)
from src.database.connection import get_session
from src.database.extraction_state import get_watermark, set_watermark
from src.database.newsletters import backfill_article_urls
from src.enums import ExtractionSource
from src.graph.client import GraphClient
from src.newsletters.medium.service import MediumService
from src.newsletters.substack import SubstackService
from src.newsletters.tldr.service import TLDRService
from src.telegram import TelegramClient
from src.telegram.utils.config import get_telegram_settings

# Email address to fetch newsletters for
GRAPH_USER_EMAIL = os.environ["GRAPH_TARGET_UPN"]

# Retry policy
NEWSLETTER_RETRY_POLICY = RetryPolicy(
    max_retries=1,
    delay=30,
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
    graph_client = GraphClient(GRAPH_USER_EMAIL)

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
        service = TLDRService(session, graph_client)
        result = service.process_digests(since=since)

        # Update watermark if we processed any newsletters
        if result.latest_received_at is not None:
            set_watermark(session, ExtractionSource.NEWSLETTER_TLDR, result.latest_received_at)
            context.log.info(f"Updated watermark to: {result.latest_received_at}")

        # Backfill any articles missing parsed URLs
        backfill_result = backfill_article_urls(session)

    stats = NewsletterStats(
        newsletters_processed=result.digests_processed,
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


@dataclass
class SubstackStats:
    """Stats for Substack processing operations."""

    posts_processed: int
    posts_new: int
    posts_duplicate: int


@op(
    name="process_substack_posts",
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Fetch and process posts from Substack publications.",
)
def process_substack_posts_op(context: OpExecutionContext) -> SubstackStats:
    """Process Substack publications using watermark-based incremental extraction.

    Fetches posts from configured Substack publications (since watermark),
    stores new posts, and updates the watermark.

    :param context: Dagster execution context.
    :returns: SubstackStats with processing statistics.
    """
    with get_session() as session:
        since = get_watermark(session, ExtractionSource.SUBSTACK)
        if since is not None:
            context.log.info(f"Using Substack watermark: {since}")
        else:
            context.log.info("No Substack watermark found, processing recent posts")

        service = SubstackService(session)
        result = service.process_publications(since=since, limit_per_publication=10)

        if result.latest_published_at is not None:
            set_watermark(session, ExtractionSource.SUBSTACK, result.latest_published_at)
            context.log.info(f"Updated Substack watermark to: {result.latest_published_at}")

    stats = SubstackStats(
        posts_processed=result.posts_processed,
        posts_new=result.posts_new,
        posts_duplicate=result.posts_duplicate,
    )

    context.log.info(
        f"Substack processing complete: {result.posts_processed} processed, "
        f"{result.posts_new} new, {result.posts_duplicate} duplicate"
    )
    return stats


@op(
    name="send_substack_alerts",
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Send Telegram alerts for new Substack posts.",
)
def send_substack_alerts_op(
    context: OpExecutionContext,
    substack_stats: SubstackStats,
) -> AlertStats:
    """Send Telegram alerts for unsent Substack posts.

    Uses the unified AlertService with SubstackAlertProvider to send
    a grouped alert for all new Substack posts.

    :param context: Dagster execution context.
    :param substack_stats: Stats from previous Substack processing op.
    :returns: AlertStats with alerting statistics.
    """
    context.log.info(f"Starting Substack alerts (processed {substack_stats.posts_new} new posts)")

    settings = get_telegram_settings()
    telegram_client = TelegramClient(
        bot_token=settings.bot_token,
        chat_id=settings.chat_id,
    )

    with get_session() as session:
        provider = SubstackAlertProvider(session)
        alert_service = AlertService(
            session=session,
            telegram_client=telegram_client,
            providers=[provider],
        )
        result = alert_service.send_alerts(alert_types=[AlertType.SUBSTACK])

    stats = AlertStats(
        newsletters_sent=result.alerts_sent,
        errors=result.errors,
    )

    context.log.info(
        f"Substack alerts complete: {result.alerts_sent} sent, {len(result.errors)} errors"
    )
    return stats


@dataclass
class MediumStats:
    """Stats for Medium digest processing operations."""

    digests_processed: int
    articles_new: int
    articles_duplicate: int


@op(
    name="process_medium_digests",
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Fetch and process Medium Daily Digests from Microsoft Graph API.",
)
def process_medium_digests_op(context: OpExecutionContext) -> MediumStats:
    """Process Medium digests using watermark-based incremental extraction.

    Fetches Medium digests from Graph API (since the last watermark),
    parses them, stores in database, and updates the watermark.

    :param context: Dagster execution context.
    :returns: MediumStats with processing statistics.
    """
    graph_client = GraphClient(GRAPH_USER_EMAIL)

    with get_session() as session:
        # Determine the since datetime
        since = get_watermark(session, ExtractionSource.NEWSLETTER_MEDIUM)
        if since is not None:
            context.log.info(f"Using Medium watermark: {since}")
        else:
            # Default to 7 days ago if no watermark is found
            since = datetime.now(UTC) - timedelta(days=7)
            context.log.info("No Medium watermark found, processing last 7 days of emails")

        # Process digests
        service = MediumService(session, graph_client)
        result = service.process_digests(since=since)

        # Update watermark if we processed any digests
        if result.latest_received_at is not None:
            set_watermark(session, ExtractionSource.NEWSLETTER_MEDIUM, result.latest_received_at)
            context.log.info(f"Updated Medium watermark to: {result.latest_received_at}")

    stats = MediumStats(
        digests_processed=result.digests_processed,
        articles_new=result.articles_new,
        articles_duplicate=result.articles_duplicate,
    )

    context.log.info(
        f"Medium processing complete: {result.digests_processed} digests, "
        f"{result.articles_new} new, {result.articles_duplicate} duplicate"
    )
    return stats


@op(
    name="send_medium_alerts",
    retry_policy=NEWSLETTER_RETRY_POLICY,
    description="Send Telegram alerts for new Medium digest articles.",
)
def send_medium_alerts_op(
    context: OpExecutionContext,
    medium_stats: MediumStats,
) -> AlertStats:
    """Send Telegram alerts for unsent Medium digests.

    Uses the unified AlertService with MediumAlertProvider to send
    alerts for digests that haven't been alerted yet.

    :param context: Dagster execution context.
    :param medium_stats: Stats from previous Medium processing op.
    :returns: AlertStats with alerting statistics.
    """
    context.log.info(f"Starting Medium alerts (processed {medium_stats.digests_processed} digests)")

    settings = get_telegram_settings()
    telegram_client = TelegramClient(
        bot_token=settings.bot_token,
        chat_id=settings.chat_id,
    )

    with get_session() as session:
        provider = MediumAlertProvider(session)
        alert_service = AlertService(
            session=session,
            telegram_client=telegram_client,
            providers=[provider],
        )
        result = alert_service.send_alerts(alert_types=[AlertType.MEDIUM])

    stats = AlertStats(
        newsletters_sent=result.alerts_sent,
        errors=result.errors,
    )

    context.log.info(
        f"Medium alerts complete: {result.alerts_sent} sent, {len(result.errors)} errors"
    )
    return stats
