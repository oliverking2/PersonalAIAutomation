"""Setup Sentry."""

import logging
import os

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


def init_sentry() -> None:
    """Initialize Sentry."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return

    # Capture ERROR logs as events, and keep INFO+ as breadcrumbs
    logging_integration = LoggingIntegration(
        level=logging.INFO,  # breadcrumbs
        event_level=logging.ERROR,  # events
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            CeleryIntegration(),
            logging_integration,
        ],
        environment=os.environ.get("APP_ENV", "local"),
        send_default_pii=False,
        traces_sample_rate=1,
    )
