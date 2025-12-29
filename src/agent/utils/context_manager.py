"""Context management for multi-turn agent conversations."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.agent.enums import CallType
from src.agent.exceptions import BedrockClientError
from src.agent.models import ConversationState, PendingConfirmation
from src.agent.utils.config import DEFAULT_AGENT_CONFIG

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.agent.bedrock_client import BedrockClient
    from src.database.agent_tracking import AgentConversation

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are a conversation summariser. Generate a concise summary that captures:
- Key facts mentioned by the user
- User preferences expressed
- Decisions made
- Outstanding questions or tasks
- Tool actions taken and their results

Focus on information useful for continuing the conversation."""


def load_conversation_state(
    conversation: AgentConversation,
) -> ConversationState:
    """Load conversation state from a database record.

    Note: We create copies of mutable collections to ensure that mutations
    to the ConversationState don't accidentally affect SQLAlchemy's tracked
    objects before an explicit save.

    :param conversation: AgentConversation record.
    :returns: ConversationState populated from the record.
    """
    pending = None
    if conversation.pending_confirmation:
        try:
            pending = PendingConfirmation.model_validate(conversation.pending_confirmation)
        except Exception as e:
            logger.warning(f"Failed to parse pending confirmation: {e}")

    # Create copies of mutable collections to avoid SQLAlchemy change detection issues
    state = ConversationState(
        conversation_id=conversation.id,
        messages=list(conversation.messages_json) if conversation.messages_json else [],
        selected_tools=list(conversation.selected_tools) if conversation.selected_tools else [],
        pending_confirmation=pending,
        summary=conversation.summary,
        message_count=conversation.message_count,
        last_summarised_at=conversation.last_summarised_at,
    )

    logger.debug(
        f"Loaded conversation state: id={conversation.id}, "
        f"messages={len(state.messages)}, pending={pending is not None}"
    )

    return state


def save_conversation_state(
    session: Session,
    conversation: AgentConversation,
    state: ConversationState,
) -> None:
    """Save conversation state to a database record.

    Note: We create copies of mutable collections (messages, selected_tools)
    to ensure SQLAlchemy detects the change. When the same list object is
    mutated in place and reassigned, SQLAlchemy may not mark it as dirty
    because the object reference hasn't changed.

    :param session: Database session.
    :param conversation: AgentConversation record to update.
    :param state: ConversationState to persist.
    """
    # Create copies to ensure SQLAlchemy detects changes to mutable JSONB fields
    conversation.messages_json = list(state.messages)
    conversation.selected_tools = list(state.selected_tools) if state.selected_tools else []
    conversation.pending_confirmation = (
        state.pending_confirmation.model_dump() if state.pending_confirmation else None
    )
    conversation.summary = state.summary
    conversation.message_count = state.message_count
    conversation.last_summarised_at = state.last_summarised_at

    session.flush()

    logger.debug(
        f"Saved conversation state: id={conversation.id}, "
        f"messages={len(state.messages)}, message_count={state.message_count}"
    )


def append_messages(
    state: ConversationState,
    new_messages: list[dict[str, Any]],
) -> None:
    """Append new messages to the conversation state.

    :param state: Conversation state to update.
    :param new_messages: New messages to append.
    """
    state.messages.extend(new_messages)
    state.message_count += len(new_messages)

    logger.debug(
        f"Appended {len(new_messages)} messages, "
        f"total={len(state.messages)}, count={state.message_count}"
    )


def should_summarise(
    state: ConversationState,
    window_size: int | None = None,
    batch_threshold: int | None = None,
) -> bool:
    """Check if the conversation needs summarisation.

    Summarisation triggers when messages exceed window_size + batch_threshold.
    This ensures we summarise in batches rather than one message at a time.

    :param state: Conversation state to check.
    :param window_size: Size of the message window to retain.
        Defaults to DEFAULT_AGENT_CONFIG.window_size.
    :param batch_threshold: Number of messages above window before summarising.
        Defaults to DEFAULT_AGENT_CONFIG.batch_threshold.
    :returns: True if summarisation is needed.
    """
    if window_size is None:
        window_size = DEFAULT_AGENT_CONFIG.window_size
    if batch_threshold is None:
        batch_threshold = DEFAULT_AGENT_CONFIG.batch_threshold
    return len(state.messages) > (window_size + batch_threshold)


def apply_sliding_window(
    state: ConversationState,
    client: BedrockClient,
    window_size: int | None = None,
    batch_threshold: int | None = None,
) -> None:
    """Apply sliding window to messages, summarising older content.

    This function:
    1. Checks if messages exceed window_size + batch_threshold
    2. If so, summarises older messages (keeping window_size recent messages)
    3. Updates the state's summary and timestamp

    The batch_threshold ensures we summarise multiple messages at once rather
    than triggering summarisation for every single message over the window.

    :param state: Conversation state to update.
    :param client: Bedrock client for summarisation.
    :param window_size: Number of recent messages to keep in full.
        Defaults to DEFAULT_AGENT_CONFIG.window_size.
    :param batch_threshold: Number of messages above window before summarising.
        Defaults to DEFAULT_AGENT_CONFIG.batch_threshold.
    """
    if window_size is None:
        window_size = DEFAULT_AGENT_CONFIG.window_size
    if batch_threshold is None:
        batch_threshold = DEFAULT_AGENT_CONFIG.batch_threshold
    if not should_summarise(state, window_size, batch_threshold):
        return

    # Messages to summarise (older than window)
    messages_to_summarise = state.messages[:-window_size]

    if not messages_to_summarise:
        return

    logger.info(f"Summarising {len(messages_to_summarise)} messages, keeping last {window_size}")

    # Generate new summary
    new_summary = _generate_summary(
        client=client,
        messages=messages_to_summarise,
        existing_summary=state.summary,
    )

    # Update state
    state.messages = state.messages[-window_size:]
    state.summary = new_summary
    state.last_summarised_at = datetime.now(UTC)

    logger.info(
        f"Applied sliding window: summary_length={len(new_summary) if new_summary else 0}, "
        f"remaining_messages={len(state.messages)}"
    )


def _generate_summary(
    client: BedrockClient,
    messages: list[dict[str, Any]],
    existing_summary: str | None,
) -> str:
    """Generate a rolling summary of messages.

    :param client: Bedrock client for LLM calls.
    :param messages: Messages to summarise.
    :param existing_summary: Previous summary to incorporate.
    :returns: New summary text.
    """
    formatted_messages = _format_messages_for_summary(messages)

    user_prompt = f"""Existing summary: {existing_summary or "None"}

New messages to incorporate:
{formatted_messages}

Generate a concise updated summary."""

    try:
        response = client.converse(
            messages=[client.create_user_message(user_prompt)],
            model_id="haiku",
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            max_tokens=512,
            temperature=0.0,
            call_type=CallType.SUMMARISER,
            cache_system_prompt=True,
        )

        return client.parse_text_response(response)

    except BedrockClientError as e:
        logger.warning(f"Summary generation failed: {e}")
        # Return existing summary if we have one
        return existing_summary or ""


def _format_messages_for_summary(messages: list[dict[str, Any]]) -> str:
    """Format messages for summarisation.

    :param messages: Bedrock message format messages.
    :returns: Human-readable message format.
    """
    lines: list[str] = []

    for msg in messages:
        role = msg.get("role", "unknown")
        content_blocks = msg.get("content", [])

        for block in content_blocks:
            if "text" in block:
                lines.append(f"{role}: {block['text']}")
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                lines.append(
                    f"{role}: [Called tool: {tool_use.get('name', 'unknown')} "
                    f"with args: {json.dumps(tool_use.get('input', {}))}]"
                )
            elif "toolResult" in block:
                tool_result = block["toolResult"]
                status = tool_result.get("status", "unknown")
                lines.append(f"{role}: [Tool result: {status}]")

    return "\n".join(lines)


def build_context_messages(state: ConversationState) -> list[dict[str, Any]]:
    """Build the context messages for an agent run.

    If a summary exists, it's prepended as a system context message.
    Then the recent messages are included.

    :param state: Conversation state with messages and summary.
    :returns: List of messages to include in the agent run.
    """
    messages: list[dict[str, Any]] = []

    # If we have a summary, include it as the first user message
    if state.summary:
        summary_message = {
            "role": "user",
            "content": [
                {
                    "text": (
                        f"[Previous conversation summary: {state.summary}]\n\n"
                        "Continue from this context."
                    )
                }
            ],
        }
        # Add a placeholder assistant acknowledgement
        assistant_ack = {
            "role": "assistant",
            "content": [{"text": "I understand the previous context. How can I help you?"}],
        }
        messages.append(summary_message)
        messages.append(assistant_ack)

    # Add recent messages
    messages.extend(state.messages)

    return messages


def clear_pending_confirmation(state: ConversationState) -> None:
    """Clear the pending confirmation from state.

    :param state: Conversation state to update.
    """
    state.pending_confirmation = None
    logger.debug("Cleared pending confirmation")


def set_pending_confirmation(
    state: ConversationState,
    pending: PendingConfirmation,
) -> None:
    """Set pending confirmation on state.

    :param state: Conversation state to update.
    :param pending: Pending confirmation details.
    """
    state.pending_confirmation = pending
    logger.debug(f"Set pending confirmation: {len(pending.tools)} tool(s)")
