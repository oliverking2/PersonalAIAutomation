"""Formatter for GlitchTip alerts to Telegram messages."""

from src.api.webhooks.glitchtip.models import GlitchTipAlert, GlitchTipAttachment
from src.messaging.telegram.utils.formatting import format_message

# Maximum length for error text preview
MAX_TEXT_LENGTH = 500


def format_glitchtip_alert(alert: GlitchTipAlert) -> tuple[str, str]:
    """Format a GlitchTip alert as a Telegram message.

    :param alert: The GlitchTip alert payload.
    :returns: Tuple of (formatted_text, parse_mode).
    """
    if not alert.attachments:
        return _format_simple_alert(alert)

    # Format the first attachment (primary error)
    attachment = alert.attachments[0]
    return _format_attachment(attachment)


def _format_simple_alert(alert: GlitchTipAlert) -> tuple[str, str]:
    """Format an alert with no attachments.

    :param alert: The GlitchTip alert payload.
    :returns: Tuple of (formatted_text, parse_mode).
    """
    lines = ["🚨 **Error Alert**", ""]

    if alert.text:
        lines.append(alert.text)

    markdown = "\n".join(lines)
    return format_message(markdown)


def _format_attachment(attachment: GlitchTipAttachment) -> tuple[str, str]:
    """Format an attachment as a Telegram message.

    :param attachment: The GlitchTip attachment.
    :returns: Tuple of (formatted_text, parse_mode).
    """
    lines = ["🚨 **Error Alert**", ""]

    # Title
    lines.append(f"**{attachment.title}**")

    # Error text preview
    if attachment.text:
        text = attachment.text
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "..."
        lines.append(f"```\n{text}\n```")

    lines.append("")

    # Metadata fields
    project = attachment.get_field_value("project")
    environment = attachment.get_field_value("environment")
    release = attachment.get_field_value("release")

    if project:
        lines.append(f"📦 Project: {project}")
    if environment:
        lines.append(f"🌍 Environment: {environment}")
    if release:
        lines.append(f"🏷️ Release: {release}")

    # Link to GlitchTip
    if attachment.title_link:
        lines.append("")
        lines.append(f"🔗 [View in GlitchTip]({attachment.title_link})")

    markdown = "\n".join(lines)
    return format_message(markdown)


def format_test_alert() -> tuple[str, str]:
    """Generate a test alert message.

    :returns: Tuple of (formatted_text, parse_mode).
    """
    lines = [
        "🧪 **Test Error Alert**",
        "",
        "**GlitchTip Integration Test**",
        "```",
        "This is a test alert to verify the webhook integration is working.",
        "```",
        "",
        "📦 Project: test-project",
        "🌍 Environment: test",
        "🏷️ Release: v0.0.0-test",
        "",
        "✅ If you see this message, the integration is working correctly.",
    ]
    markdown = "\n".join(lines)
    return format_message(markdown)
