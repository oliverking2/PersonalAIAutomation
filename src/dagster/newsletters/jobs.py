"""Dagster jobs for newsletter automation."""

from dagster import job
from src.dagster.newsletters.ops import process_newsletters_op, send_alerts_op


@job(description="Process newsletters and send Telegram alerts.")
def newsletter_pipeline_job() -> None:
    """Newsletter processing pipeline.

    Sequential workflow:
    1. Fetch and process newsletters from Graph API
    2. Send Telegram alerts for any unsent newsletters
    """
    newsletter_stats = process_newsletters_op()
    send_alerts_op(newsletter_stats)
