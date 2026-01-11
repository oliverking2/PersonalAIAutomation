"""Formatter for GlitchTip alerts to Telegram HTML messages."""

import html

from src.api.webhooks.glitchtip.models import GlitchTipAlert, GlitchTipAttachment

# Maximum length for error text preview
MAX_TEXT_LENGTH = 500


def format_glitchtip_alert(alert: GlitchTipAlert) -> str:
    """Format a GlitchTip alert as a Telegram HTML message.

    :param alert: The GlitchTip alert payload.
    :returns: HTML-formatted message for Telegram.
    """
    if not alert.attachments:
        return _format_simple_alert(alert)

    # Format the first attachment (primary error)
    attachment = alert.attachments[0]
    return _format_attachment(attachment)


def _format_simple_alert(alert: GlitchTipAlert) -> str:
    """Format an alert with no attachments.

    :param alert: The GlitchTip alert payload.
    :returns: HTML-formatted message.
    """
    lines = ["🚨 <b>Error Alert</b>", ""]

    if alert.text:
        lines.append(html.escape(alert.text))

    return "\n".join(lines)


def _format_attachment(attachment: GlitchTipAttachment) -> str:
    """Format an attachment as a Telegram HTML message.

    :param attachment: The GlitchTip attachment.
    :returns: HTML-formatted message.
    """
    lines = ["🚨 <b>Error Alert</b>", ""]

    # Title
    lines.append(f"<b>{html.escape(attachment.title)}</b>")

    # Error text preview
    if attachment.text:
        text = attachment.text
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "..."
        lines.append(f"<pre>{html.escape(text)}</pre>")

    lines.append("")

    # Metadata fields
    project = attachment.get_field_value("project")
    environment = attachment.get_field_value("environment")
    release = attachment.get_field_value("release")

    if project:
        lines.append(f"📦 Project: {html.escape(project)}")
    if environment:
        lines.append(f"🌍 Environment: {html.escape(environment)}")
    if release:
        lines.append(f"🏷️ Release: {html.escape(release)}")

    # Link to GlitchTip
    if attachment.title_link:
        lines.append("")
        lines.append(f'🔗 <a href="{attachment.title_link}">View in GlitchTip</a>')

    return "\n".join(lines)


def format_test_alert() -> str:
    """Generate a test alert message.

    :returns: HTML-formatted test message for Telegram.
    """
    lines = [
        "🧪 <b>Test Error Alert</b>",
        "",
        "<b>GlitchTip Integration Test</b>",
        "<pre>This is a test alert to verify the webhook integration is working.</pre>",
        "",
        "📦 Project: test-project",
        "🌍 Environment: test",
        "🏷️ Release: v0.0.0-test",
        "",
        "✅ If you see this message, the integration is working correctly.",
    ]
    return "\n".join(lines)
