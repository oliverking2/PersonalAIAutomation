"""Confidence classifier for action intent in the AI agent module.

Classifies whether a proposed action was explicitly requested by the user
or requires confirmation (inferred/proactive).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import CallType, ConfidenceLevel
from src.agent.exceptions import BedrockClientError
from src.agent.utils.config import DEFAULT_AGENT_CONFIG

logger = logging.getLogger(__name__)

CONFIDENCE_CLASSIFIER_SYSTEM_PROMPT = """You are classifying user intent for a proposed action based on a conversation.

Classify as:
- EXPLICIT: User directly and clearly requested this specific action. This includes:
  - Direct requests: "update X to Y", "tidy up X", "fix the typo in X", "change X"
  - Confirming a choice: Agent asked "which issues?" and user said "both"
  - Clear follow-ups to their own request
- NEEDS_CONFIRMATION: Agent is inferring, interpreting vaguely, or suggesting unprompted:
  - Vague requests: User said "clean up my tasks" without specifying which tasks or what to clean
  - Proactive suggestions: Agent noticed something and is offering to fix it
  - Ambiguous scope: User's request could apply to multiple items

When uncertain, default to NEEDS_CONFIRMATION.

Respond with valid JSON only, no other text:
{
  "level": "explicit" | "needs_confirmation",
  "reasoning": "brief explanation"
}"""


class ConfidenceClassificationParseError(Exception):
    """Raised when confidence classification response cannot be parsed."""

    pass


class ConfidenceClassification(BaseModel):
    """Result of confidence classification.

    :param level: The confidence level (explicit or needs_confirmation).
    :param reasoning: Brief explanation for the classification.
    """

    level: ConfidenceLevel
    reasoning: str


def extract_conversation_for_classification(
    messages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Extract only user messages and agent text responses for classification.

    Filters out tool calls, tool results, and system content to keep
    the classification context minimal and focused on user intent.

    :param messages: Full conversation messages from Bedrock format.
    :returns: Filtered messages with only user/assistant text.
    """
    filtered: list[dict[str, str]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content", [])

        if role == "user":
            # Extract text from user messages, skip toolResult blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)

            if text_parts:
                filtered.append({"role": "user", "text": " ".join(text_parts)})

        elif role == "assistant":
            # Extract text from assistant messages, skip toolUse blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    text_parts.append(block["text"])

            if text_parts:
                filtered.append({"role": "assistant", "text": " ".join(text_parts)})

    return filtered


def _format_conversation_for_prompt(messages: list[dict[str, str]]) -> str:
    """Format filtered messages into a readable conversation string.

    :param messages: Filtered messages from extract_conversation_for_classification.
    :returns: Formatted conversation string.
    """
    lines = []
    for msg in messages:
        role = msg["role"].capitalize()
        text = msg["text"]
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def classify_action_confidence(
    client: BedrockClient,
    messages: list[dict[str, Any]],
    proposed_action: str,
) -> ConfidenceClassification:
    """Classify whether the user explicitly requested this action.

    Uses Haiku for fast, cheap classification. Extracts only user messages
    and agent text responses (no tool calls/results) to keep context minimal.

    :param client: Bedrock client for LLM calls.
    :param messages: Full conversation messages (will be filtered).
    :param proposed_action: Human-readable description of the action.
    :returns: Classification result.
    :raises ConfidenceClassificationParseError: If classification fails after retries.
    """
    max_retries = DEFAULT_AGENT_CONFIG.max_classification_retries

    # Filter conversation to just user/assistant text
    filtered = extract_conversation_for_classification(messages)
    conversation_text = _format_conversation_for_prompt(filtered)

    user_prompt = f"""<conversation>
{conversation_text}
</conversation>

Proposed action: "{proposed_action}"

Classify whether this action was explicitly requested by the user."""

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.converse(
                messages=[client.create_user_message(user_prompt)],
                model_id="haiku",
                system_prompt=CONFIDENCE_CLASSIFIER_SYSTEM_PROMPT,
                max_tokens=256,
                temperature=0.0,
                call_type=CallType.CLASSIFIER,
                cache_system_prompt=True,
            )

            response_text = client.parse_text_response(response)
            result = _parse_confidence_classification_response(response_text)

            logger.info(
                f"Confidence classification: action='{proposed_action[:50]}...', "
                f"level={result.level}, reasoning='{result.reasoning[:50]}...'"
            )

            return result

        except ConfidenceClassificationParseError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Confidence classification parse failed (attempt {attempt + 1}/"
                    f"{max_retries + 1}), retrying: {e}"
                )
            continue

        except BedrockClientError as e:
            logger.error(f"Confidence classification API call failed: {e}")
            # Default to NEEDS_CONFIRMATION on API failure (safe fallback)
            logger.warning("Defaulting to NEEDS_CONFIRMATION due to API failure")
            return ConfidenceClassification(
                level=ConfidenceLevel.NEEDS_CONFIRMATION,
                reasoning=f"API call failed: {e}",
            )

    # All retries exhausted - default to NEEDS_CONFIRMATION (safe fallback)
    logger.warning(
        f"Confidence classification failed after {max_retries + 1} attempts, "
        f"defaulting to NEEDS_CONFIRMATION: {last_error}"
    )
    return ConfidenceClassification(
        level=ConfidenceLevel.NEEDS_CONFIRMATION,
        reasoning=f"Classification failed after retries: {last_error}",
    )


def _parse_confidence_classification_response(
    response_text: str,
) -> ConfidenceClassification:
    """Parse the confidence classification response from the LLM.

    :param response_text: Raw text response from the LLM.
    :returns: Parsed confidence classification.
    :raises ConfidenceClassificationParseError: If the response cannot be parsed.
    """
    # Extract JSON from markdown code blocks if present
    text = BedrockClient.extract_json_from_markdown(response_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfidenceClassificationParseError(f"Invalid JSON in response: {e}") from e

    level_str = data.get("level")
    if level_str is None:
        raise ConfidenceClassificationParseError("Response missing 'level' field")

    level_str = level_str.lower()

    level_map = {
        "explicit": ConfidenceLevel.EXPLICIT,
        "needs_confirmation": ConfidenceLevel.NEEDS_CONFIRMATION,
    }

    level = level_map.get(level_str)
    if level is None:
        raise ConfidenceClassificationParseError(f"Unknown level value: {level_str}")

    reasoning = data.get("reasoning", "")

    return ConfidenceClassification(level=level, reasoning=reasoning)
