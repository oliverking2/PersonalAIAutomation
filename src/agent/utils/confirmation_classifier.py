"""Confirmation response classifier for the AI agent module."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import CallType, ConfirmationType, ToolDecisionType
from src.agent.exceptions import BedrockClientError
from src.agent.utils.config import DEFAULT_AGENT_CONFIG

if TYPE_CHECKING:
    from src.agent.models import PendingConfirmation, PendingToolAction

logger = logging.getLogger(__name__)


class ClassificationParseError(Exception):
    """Raised when classification response cannot be parsed."""

    pass


class ToolDecision(BaseModel):
    """Decision for a single tool in a batch confirmation.

    :param index: 1-based index of the tool.
    :param decision: The decision type (approve/reject/modify).
    :param correction: Natural language correction if decision is MODIFY.
    """

    index: int
    decision: ToolDecisionType
    correction: str | None = None


class BatchClassificationResult(BaseModel):
    """Result of batch confirmation classification.

    :param classification: Overall classification type.
    :param tool_decisions: Per-tool decisions (only for PARTIAL_CONFIRM).
    """

    classification: ConfirmationType
    tool_decisions: list[ToolDecision] = Field(default_factory=list)


BATCH_CLASSIFIER_SYSTEM_PROMPT = """You are a confirmation classifier for multiple pending actions. Given a list of pending actions and a user's response, determine:

1. If the user wants to proceed with ALL actions as-is, return:
   {{"classification": "CONFIRM"}}

2. If the user wants to cancel ALL actions, return:
   {{"classification": "DENY"}}

3. If the user's message is a new request unrelated to the confirmation, return:
   {{"classification": "NEW_INTENT"}}

4. If the user wants to:
   - Approve some actions but not others, OR
   - Modify any action's parameters, OR
   - Provide corrections to any action

   Return PARTIAL_CONFIRM with per-tool decisions:
   {{
     "classification": "PARTIAL_CONFIRM",
     "tool_decisions": [
       {{"index": 1, "decision": "approve"}},
       {{"index": 2, "decision": "reject"}},
       {{"index": 3, "decision": "modify", "correction": "change priority to High"}}
     ]
   }}

Decision types:
- "approve": Execute the action as-is
- "reject": Skip this action
- "modify": Execute with the correction applied (include the correction text)

Examples:
- "yes" or "go ahead" → CONFIRM (all approved)
- "no" or "cancel" → DENY (all cancelled)
- "yes to 1 and 2, skip 3" → PARTIAL_CONFIRM with approve/approve/reject
- "yes but change the priority to High" → PARTIAL_CONFIRM with modify decision
- "yes to all except the last one" → PARTIAL_CONFIRM with appropriate decisions
- "what about X instead?" → NEW_INTENT

Respond with valid JSON only, no other text."""


CORRECTION_APPLICATOR_SYSTEM_PROMPT = """You are a tool argument modifier. Given a tool's current arguments and a natural language correction, update the arguments to reflect the correction.

Return ONLY valid JSON with the updated arguments. Do not include any explanation.

If the correction cannot be applied (e.g., refers to a field that doesn't exist), return the original arguments unchanged.

Example:
Tool: create_task
Current args: {{"title": "Buy groceries", "priority": "low"}}
Correction: "change priority to High"
Output: {{"title": "Buy groceries", "priority": "high"}}"""


def classify_batch_confirmation_response(
    client: BedrockClient,
    user_message: str,
    pending: PendingConfirmation,
) -> BatchClassificationResult:
    """Classify a user's response to a batch confirmation request.

    Uses Haiku to determine if the user's message is a full confirmation,
    denial, new intent, or partial confirmation with per-tool decisions.

    Retries on parse failures up to max_classification_retries times.

    :param client: Bedrock client for LLM calls.
    :param user_message: The user's response message.
    :param pending: The pending confirmation with list of tools.
    :returns: Classification result with optional per-tool decisions.
    """
    max_retries = DEFAULT_AGENT_CONFIG.max_classification_retries

    # Build actions list for the prompt
    actions_list = "\n".join(f"{tool.index}. {tool.action_summary}" for tool in pending.tools)

    user_prompt = f"""Pending actions:
{actions_list}

User's response: "{user_message}"

Classify this response. If the user provides per-action decisions, include tool_decisions."""

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.converse(
                messages=[client.create_user_message(user_prompt)],
                model_id="haiku",
                system_prompt=BATCH_CLASSIFIER_SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.0,
                call_type=CallType.CLASSIFIER,
                cache_system_prompt=True,
            )

            response_text = client.parse_text_response(response)
            result = _parse_batch_classification_response(response_text, len(pending.tools))

            logger.info(
                f"Batch confirmation classification: message='{user_message[:50]}...', "
                f"result={result.classification}, decisions={len(result.tool_decisions)}"
            )

            return result

        except ClassificationParseError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Batch classification parse failed (attempt {attempt + 1}/"
                    f"{max_retries + 1}), retrying: {e}"
                )
            continue

        except BedrockClientError as e:
            logger.error(f"Batch classification API call failed: {e}")
            raise ClassificationParseError(f"Classification API call failed: {e}") from e

    # All retries exhausted - raise error instead of silently defaulting
    logger.error(f"Batch classification failed after {max_retries + 1} attempts: {last_error}")
    raise ClassificationParseError(
        f"Failed to classify response after {max_retries + 1} attempts: {last_error}"
    )


def apply_correction(
    client: BedrockClient,
    tool: PendingToolAction,
    correction: str,
) -> dict[str, Any]:
    """Apply a natural language correction to tool arguments.

    Uses Haiku to interpret the correction and update the arguments.

    :param client: Bedrock client for LLM calls.
    :param tool: The pending tool action with current arguments.
    :param correction: Natural language correction from the user.
    :returns: Updated arguments dictionary.
    :raises ClassificationParseError: If the correction cannot be applied.
    """
    max_retries = DEFAULT_AGENT_CONFIG.max_classification_retries

    user_prompt = f"""Tool: {tool.tool_name}
Current args: {json.dumps(tool.input_args)}
Correction: "{correction}"

Return the updated arguments as JSON."""

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.converse(
                messages=[client.create_user_message(user_prompt)],
                model_id="haiku",
                system_prompt=CORRECTION_APPLICATOR_SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.0,
                call_type=CallType.CLASSIFIER,
                cache_system_prompt=True,
            )

            response_text = client.parse_text_response(response)
            updated_args = _parse_correction_response(response_text)

            logger.info(f"Applied correction to {tool.tool_name}: '{correction[:50]}...'")

            return updated_args

        except ClassificationParseError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Correction parse failed (attempt {attempt + 1}/"
                    f"{max_retries + 1}), retrying: {e}"
                )
            continue

        except BedrockClientError as e:
            logger.error(f"Correction API call failed: {e}")
            raise ClassificationParseError(f"Correction API call failed: {e}") from e

    # All retries exhausted - raise error
    logger.error(f"Correction failed after {max_retries + 1} attempts: {last_error}")
    raise ClassificationParseError(
        f"Failed to apply correction after {max_retries + 1} attempts: {last_error}"
    )


def _parse_batch_classification_response(
    response_text: str,
    tool_count: int,
) -> BatchClassificationResult:
    """Parse the batch classification response from the LLM.

    :param response_text: Raw text response from the LLM.
    :param tool_count: Number of tools in the batch (for validation).
    :returns: Parsed batch classification result.
    :raises ClassificationParseError: If the response cannot be parsed.
    """
    text = BedrockClient.extract_json_from_markdown(response_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClassificationParseError(f"Invalid JSON in response: {e}") from e

    classification_str = data.get("classification")
    if classification_str is None:
        raise ClassificationParseError("Response missing 'classification' field")

    classification_str = classification_str.upper()

    # Map string to enum
    classification_map = {
        "CONFIRM": ConfirmationType.CONFIRM,
        "DENY": ConfirmationType.DENY,
        "NEW_INTENT": ConfirmationType.NEW_INTENT,
        "PARTIAL_CONFIRM": ConfirmationType.PARTIAL_CONFIRM,
    }

    classification = classification_map.get(classification_str)
    if classification is None:
        raise ClassificationParseError(f"Unknown classification value: {classification_str}")

    # Parse tool decisions if present
    tool_decisions: list[ToolDecision] = []
    if classification == ConfirmationType.PARTIAL_CONFIRM:
        raw_decisions = data.get("tool_decisions", [])
        if not raw_decisions:
            raise ClassificationParseError(
                "PARTIAL_CONFIRM requires tool_decisions but none provided"
            )

        for raw_decision in raw_decisions:
            index = raw_decision.get("index")
            decision_str = raw_decision.get("decision", "").lower()
            correction = raw_decision.get("correction")

            if index is None or not isinstance(index, int):
                raise ClassificationParseError(f"Invalid tool decision index: {raw_decision}")

            if index < 1 or index > tool_count:
                raise ClassificationParseError(
                    f"Tool decision index {index} out of range (1-{tool_count})"
                )

            decision_map = {
                "approve": ToolDecisionType.APPROVE,
                "reject": ToolDecisionType.REJECT,
                "modify": ToolDecisionType.MODIFY,
            }

            decision = decision_map.get(decision_str)
            if decision is None:
                raise ClassificationParseError(f"Unknown decision type: {decision_str}")

            if decision == ToolDecisionType.MODIFY and not correction:
                raise ClassificationParseError(
                    f"MODIFY decision for tool {index} requires correction text"
                )

            tool_decisions.append(
                ToolDecision(index=index, decision=decision, correction=correction)
            )

    return BatchClassificationResult(
        classification=classification,
        tool_decisions=tool_decisions,
    )


def _parse_correction_response(response_text: str) -> dict[str, Any]:
    """Parse the correction response from the LLM.

    :param response_text: Raw text response from the LLM.
    :returns: Updated arguments dictionary.
    :raises ClassificationParseError: If the response cannot be parsed.
    """
    text = BedrockClient.extract_json_from_markdown(response_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClassificationParseError(f"Invalid JSON in correction response: {e}") from e

    if not isinstance(data, dict):
        raise ClassificationParseError(f"Correction response must be a dict, got {type(data)}")

    return data
