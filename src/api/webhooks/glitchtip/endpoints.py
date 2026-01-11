"""GlitchTip webhook endpoints."""

import logging
import os
import secrets

from fastapi import APIRouter, HTTPException, Query, status

from src.api.webhooks.glitchtip.formatter import format_glitchtip_alert, format_test_alert
from src.api.webhooks.glitchtip.models import GlitchTipAlert, WebhookResponse
from src.messaging.telegram.client import TelegramClient, TelegramClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/glitchtip", tags=["Webhooks"])


def _get_webhook_secret() -> str:
    """Get the GlitchTip webhook secret from environment.

    :returns: The webhook secret.
    :raises ValueError: If not configured.
    """
    secret = os.environ.get("GLITCHTIP_WEBHOOK_SECRET")
    if not secret:
        raise ValueError("GLITCHTIP_WEBHOOK_SECRET not configured")
    return secret


def _get_telegram_client() -> TelegramClient:
    """Get a Telegram client configured for error alerts.

    :returns: Configured TelegramClient.
    :raises ValueError: If required environment variables are not set.
    """
    bot_token = os.environ.get("TELEGRAM_ERROR_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_ERROR_CHAT_ID")

    if not bot_token:
        raise ValueError("TELEGRAM_ERROR_BOT_TOKEN not configured")
    if not chat_id:
        raise ValueError("TELEGRAM_ERROR_CHAT_ID not configured")

    return TelegramClient(bot_token=bot_token, chat_id=chat_id)


def _verify_token(token: str | None) -> None:
    """Verify the webhook token.

    :param token: The token from the query parameter.
    :raises HTTPException: If token is invalid or missing.
    """
    if not token:
        logger.warning("GlitchTip webhook called without token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    try:
        expected = _get_webhook_secret()
    except ValueError as e:
        logger.error(f"Webhook secret configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook authentication not configured",
        ) from e

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(token, expected):
        logger.warning("GlitchTip webhook called with invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


@router.post(
    "",
    response_model=WebhookResponse,
    summary="Receive GlitchTip error alert",
    description="Receives a GlitchTip webhook payload and forwards it to Telegram.",
)
def receive_glitchtip_webhook(
    alert: GlitchTipAlert,
    token: str | None = Query(None, description="Webhook authentication token"),
) -> WebhookResponse:
    """Receive and process a GlitchTip webhook.

    :param alert: The GlitchTip alert payload.
    :param token: Authentication token from query parameter.
    :returns: Webhook processing result.
    :raises HTTPException: If authentication fails or sending fails.
    """
    _verify_token(token)

    logger.info("Received GlitchTip webhook")

    # Format the alert for Telegram
    message, parse_mode = format_glitchtip_alert(alert)

    # Send to Telegram
    try:
        client = _get_telegram_client()
        client.send_message_sync(message, parse_mode=parse_mode)
        logger.info("GlitchTip alert forwarded to Telegram")
    except ValueError as e:
        logger.error(f"Telegram configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram not configured",
        ) from e
    except TelegramClientError as e:
        logger.exception("Failed to send GlitchTip alert to Telegram")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send to Telegram: {e}",
        ) from e

    return WebhookResponse(status="ok", message="Alert forwarded to Telegram")


@router.post(
    "/test",
    response_model=WebhookResponse,
    summary="Send test error alert",
    description="Sends a test alert to Telegram to verify the integration is working.",
)
def send_test_alert(
    token: str | None = Query(None, description="Webhook authentication token"),
) -> WebhookResponse:
    """Send a test alert to verify the integration.

    :param token: Authentication token from query parameter.
    :returns: Webhook processing result.
    :raises HTTPException: If authentication fails or sending fails.
    """
    _verify_token(token)

    logger.info("Sending GlitchTip test alert")

    # Generate test message
    message, parse_mode = format_test_alert()

    # Send to Telegram
    try:
        client = _get_telegram_client()
        client.send_message_sync(message, parse_mode=parse_mode)
        logger.info("GlitchTip test alert sent to Telegram")
    except ValueError as e:
        logger.error(f"Telegram configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram not configured",
        ) from e
    except TelegramClientError as e:
        logger.exception("Failed to send test alert to Telegram")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send to Telegram: {e}",
        ) from e

    return WebhookResponse(status="ok", message="Test alert sent to Telegram")


class GlitchTipTestError(Exception):
    """Test exception to verify GlitchTip error tracking."""

    pass


@router.post(
    "/trigger-error",
    response_model=WebhookResponse,
    summary="Trigger a test error",
    description="Raises an unhandled exception to verify GlitchTip is capturing errors.",
)
def trigger_test_error(
    token: str | None = Query(None, description="Webhook authentication token"),
) -> WebhookResponse:
    """Trigger an unhandled exception to test error tracking.

    This endpoint intentionally raises an exception that should be captured
    by GlitchTip/Sentry to verify the error tracking integration is working.

    :param token: Authentication token from query parameter.
    :returns: Never returns - always raises an exception.
    :raises GlitchTipTestError: Always raised to test error tracking.
    """
    _verify_token(token)

    logger.info("Triggering test error for GlitchTip verification")
    raise GlitchTipTestError(
        "This is a test error to verify GlitchTip is capturing exceptions correctly."
    )
