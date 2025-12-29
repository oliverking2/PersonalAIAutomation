"""Dagster jobs for newsletter automation."""

from dagster import job
from src.dagster.newsletters.ops import (
    process_newsletters_op,
    process_substack_posts_op,
    send_alerts_op,
    send_substack_alerts_op,
)


@job(description="Process newsletters and send Telegram alerts.")
def newsletter_pipeline_job() -> None:
    """Newsletter processing pipeline.

    Sequential workflow:
    1. Fetch and process newsletters from Graph API
    2. Send Telegram alerts for any unsent newsletters
    """
    newsletter_stats = process_newsletters_op()
    send_alerts_op(newsletter_stats)


@job(description="Process Substack posts and send Telegram alerts.")
def substack_pipeline_job() -> None:
    """Substack processing pipeline.

    Sequential workflow:
    1. Fetch and process posts from Substack publications
    2. Send Telegram alert with all new posts grouped by publication
    """
    substack_stats = process_substack_posts_op()
    send_substack_alerts_op(substack_stats)
