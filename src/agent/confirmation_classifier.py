"""Confirmation response classifier for the AI agent module."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import CallType, ConfirmationType
from src.agent.exceptions import BedrockClientError

if TYPE_CHECKING:
    from src.agent.models import PendingConfirmation

logger = logging.getLogger(__name__)

# Maximum number of retries for classification
MAX_CLASSIFICATION_RETRIES = 2

CLASSIFIER_SYSTEM_PROMPT = """You are a confirmation classifier. Given a pending action and a user's response, determine if the user is:
1. CONFIRM - agreeing to proceed (e.g., "yes", "yep", "sure", "go ahead", "do it", "ok", "sounds good")
2. DENY - declining the action (e.g., "no", "stop", "cancel", "don't", "wait", "never mind", "actually no")
3. NEW_INTENT - providing a new request unrelated to the confirmation (e.g., "what about...", "can you also...", "show me something else")

Respond with valid JSON only, no other text:
{{
  "classification": "CONFIRM" | "DENY" | "NEW_INTENT"
}}

If you are unable to determine the classification, respond with {"classification": "NEW_INTENT"}.

Example:
Input: "yes, go ahead"
Output: {"classification": "CONFIRM"}

Input: "no, cancel"
Output: {"classification": "DENY"}

Input: "what about..."
Output: {"classification": "NEW_INTENT"}
"""


class ClassificationParseError(Exception):
    """Raised when classification response cannot be parsed."""

    pass


def classify_confirmation_response(
    client: BedrockClient,
    user_message: str,
    pending: PendingConfirmation,
) -> ConfirmationType:
    """Classify a user's response to a confirmation request.

    Uses Haiku to determine if the user's message is a confirmation,
    denial, or a new intent unrelated to the pending action.

    Retries on parse failures up to MAX_CLASSIFICATION_RETRIES times.

    :param client: Bedrock client for LLM calls.
    :param user_message: The user's response message.
    :param pending: The pending confirmation details.
    :returns: Classification of the user's response.
    """
    user_prompt = f"""Pending action: {pending.action_summary}
Tool: {pending.tool_name}
Arguments: {pending.input_args}

User's response: "{user_message}"

Classify this response."""

    last_error: Exception | None = None

    for attempt in range(MAX_CLASSIFICATION_RETRIES + 1):
        try:
            response = client.converse(
                messages=[client.create_user_message(user_prompt)],
                model_id="haiku",
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                max_tokens=128,
                temperature=0.0,
                call_type=CallType.CLASSIFIER,
                cache_system_prompt=True,
            )

            response_text = client.parse_text_response(response)
            classification = _parse_classification_response(response_text)

            logger.info(
                f"Confirmation classification: message='{user_message[:50]}...', "
                f"result={classification}"
            )

            return classification

        except ClassificationParseError as e:
            last_error = e
            if attempt < MAX_CLASSIFICATION_RETRIES:
                logger.warning(
                    f"Classification parse failed (attempt {attempt + 1}/"
                    f"{MAX_CLASSIFICATION_RETRIES + 1}), retrying: {e}"
                )
            continue

        except BedrockClientError as e:
            logger.error(f"Classification API call failed: {e}")
            raise ClassificationParseError(f"Classification API call failed: {e}") from e

    # All retries exhausted - raise error instead of silently defaulting
    logger.error(
        f"Classification failed after {MAX_CLASSIFICATION_RETRIES + 1} attempts: {last_error}"
    )
    raise ClassificationParseError(
        f"Failed to classify response after {MAX_CLASSIFICATION_RETRIES + 1} attempts: {last_error}"
    )


def _parse_classification_response(response_text: str) -> ConfirmationType:
    """Parse the classification response from the LLM.

    :param response_text: Raw text response from the LLM.
    :returns: Parsed confirmation type.
    :raises ClassificationParseError: If the response cannot be parsed.
    """
    # Extract JSON from markdown code blocks if present (Haiku often ignores instructions)
    text = BedrockClient.extract_json_from_markdown(response_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClassificationParseError(f"Invalid JSON in response: {e}") from e

    classification_str = data.get("classification")
    if classification_str is None:
        raise ClassificationParseError("Response missing 'classification' field")

    classification_str = classification_str.upper()

    if classification_str == "CONFIRM":
        return ConfirmationType.CONFIRM
    if classification_str == "DENY":
        return ConfirmationType.DENY
    if classification_str == "NEW_INTENT":
        return ConfirmationType.NEW_INTENT

    raise ClassificationParseError(f"Unknown classification value: {classification_str}")
