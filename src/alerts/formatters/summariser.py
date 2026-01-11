"""AI-powered text summarisation for alert descriptions."""

import logging

from src.agent.bedrock_client import BedrockClient
from src.agent.exceptions import BedrockClientError

logger = logging.getLogger(__name__)


def summarise_description(description: str, max_length: int = 150) -> str:
    """Summarise a description to fit within max_length characters.

    If the description is already short enough, returns it unchanged.
    If summarisation fails, falls back to truncation with ellipsis.

    :param description: The description to summarise.
    :param max_length: Maximum length for the summary.
    :returns: Summarised or original description.
    """
    if len(description) <= max_length:
        return description

    try:
        return _generate_summary(description, max_length)
    except BedrockClientError:
        logger.exception("Failed to summarise description, falling back to truncation")
        return _truncate_with_ellipsis(description, max_length)


def _generate_summary(description: str, max_length: int) -> str:
    """Generate an AI summary of the description.

    :param description: Text to summarise.
    :param max_length: Target maximum length.
    :returns: AI-generated summary.
    :raises BedrockClientError: If the API call fails.
    """
    client = BedrockClient()

    prompt = f"""Summarise the following text in {max_length} characters or fewer.
Keep the key information and maintain a professional tone.
Return ONLY the summary, no quotes or explanation.

Text: {description}"""

    response = client.converse(
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        model_id="haiku",
        system_prompt="You are a concise summariser. Output only the summary.",
        max_tokens=100,
        temperature=0.0,
        cache_system_prompt=True,
    )

    summary = client.parse_text_response(response).strip()

    # Ensure we don't exceed max_length
    if len(summary) > max_length:
        return _truncate_with_ellipsis(summary, max_length)

    return summary


def _truncate_with_ellipsis(text: str, max_length: int) -> str:
    """Truncate text with ellipsis at word boundary.

    :param text: Text to truncate.
    :param max_length: Maximum length including ellipsis.
    :returns: Truncated text with ellipsis.
    """
    if len(text) <= max_length:
        return text

    # Leave room for ellipsis
    truncated = text[: max_length - 3]

    # Try to break at word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + "..."
