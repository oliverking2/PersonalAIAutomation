"""Database operations for agent tracking."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, joinedload

from src.database.agent_tracking.models import AgentConversation, AgentRun, LLMCall

if TYPE_CHECKING:
    from src.agent.call_tracking import LLMCallRecord, TrackingContext

logger = logging.getLogger(__name__)


def create_agent_conversation(
    session: Session,
    external_id: str | None = None,
) -> AgentConversation:
    """Create a new agent conversation.

    :param session: Database session.
    :param external_id: Optional external identifier.
    :returns: The created conversation.
    """
    conversation = AgentConversation(external_id=external_id)
    session.add(conversation)
    session.flush()
    logger.info(f"Created agent conversation: id={conversation.id}")
    return conversation


def get_agent_conversation_by_id(
    session: Session,
    conversation_id: uuid.UUID,
) -> AgentConversation:
    """Get an agent conversation by ID.

    :param session: Database session.
    :param conversation_id: The conversation ID.
    :returns: The conversation.
    :raises NoResultFound: If not found.
    """
    return session.query(AgentConversation).filter(AgentConversation.id == conversation_id).one()


def end_agent_conversation(
    session: Session,
    conversation_id: uuid.UUID,
) -> AgentConversation:
    """Mark an agent conversation as ended.

    :param session: Database session.
    :param conversation_id: The conversation ID.
    :returns: The updated conversation.
    """
    conversation = get_agent_conversation_by_id(session, conversation_id)
    conversation.ended_at = datetime.now(UTC)
    session.flush()
    logger.info(f"Ended agent conversation: id={conversation_id}")
    return conversation


def create_agent_run(
    session: Session,
    conversation_id: uuid.UUID,
    user_message: str,
) -> AgentRun:
    """Create a new agent run.

    :param session: Database session.
    :param conversation_id: Parent conversation ID.
    :param user_message: The user's input message.
    :returns: The created agent run.
    """
    agent_run = AgentRun(
        conversation_id=conversation_id,
        user_message=user_message,
        stop_reason="pending",
    )
    session.add(agent_run)
    session.flush()
    logger.debug(f"Created agent run: id={agent_run.id}")
    return agent_run


def _llm_call_from_record(
    call_record: LLMCallRecord,
    agent_run_id: uuid.UUID | None = None,
) -> LLMCall:
    """Create an LLMCall model from an LLMCallRecord.

    :param call_record: The LLM call record from tracking context.
    :param agent_run_id: Optional agent run ID if part of an agent run.
    :returns: The LLMCall model instance (not yet added to session).
    """
    return LLMCall(
        id=call_record.id,
        agent_run_id=agent_run_id,
        model_alias=call_record.model_alias,
        model_id=call_record.model_id,
        call_type=call_record.call_type,
        request_messages=call_record.request_messages,
        response_content=call_record.response_content,
        input_tokens=call_record.input_tokens,
        output_tokens=call_record.output_tokens,
        cache_read_tokens=call_record.cache_read_tokens,
        estimated_cost_usd=call_record.estimated_cost_usd,
        latency_ms=call_record.latency_ms,
        called_at=call_record.called_at,
    )


def complete_agent_run(  # noqa: PLR0913 - Agent run completion requires multiple parameters
    session: Session,
    agent_run_id: uuid.UUID,
    tracking_context: TrackingContext,
    final_response: str,
    stop_reason: str,
    steps_taken: int,
) -> AgentRun:
    """Complete an agent run with tracking data.

    :param session: Database session.
    :param agent_run_id: The agent run ID.
    :param tracking_context: Tracking context with LLM call records.
    :param final_response: The agent's final response.
    :param stop_reason: Reason the agent stopped.
    :param steps_taken: Number of tool execution steps.
    :returns: The updated agent run.
    """
    agent_run = session.query(AgentRun).filter(AgentRun.id == agent_run_id).one()

    agent_run.final_response = final_response
    agent_run.stop_reason = stop_reason
    agent_run.steps_taken = steps_taken
    agent_run.ended_at = datetime.now(UTC)
    agent_run.total_input_tokens = tracking_context.total_input_tokens
    agent_run.total_output_tokens = tracking_context.total_output_tokens
    agent_run.total_cache_read_tokens = tracking_context.total_cache_read_tokens
    agent_run.total_estimated_cost_usd = tracking_context.total_estimated_cost

    # Create LLM call records
    for call_record in tracking_context.llm_calls:
        llm_call = _llm_call_from_record(call_record, agent_run_id)
        session.add(llm_call)

    session.flush()

    # Update conversation totals
    _update_conversation_totals(session, agent_run.conversation_id)

    logger.info(
        f"Completed agent run: id={agent_run_id}, "
        f"tokens={agent_run.total_input_tokens}/{agent_run.total_output_tokens}, "
        f"cost=${agent_run.total_estimated_cost_usd}"
    )

    return agent_run


def create_llm_call(
    session: Session,
    call_record: LLMCallRecord,
    agent_run_id: uuid.UUID | None = None,
) -> LLMCall:
    """Create an LLM call record in the database.

    Use this for standalone LLM calls that are not part of an agent run,
    such as direct BedrockClient usage.

    :param session: Database session.
    :param call_record: The LLM call record from tracking context.
    :param agent_run_id: Optional agent run ID if part of an agent run.
    :returns: The created LLM call.
    """
    llm_call = _llm_call_from_record(call_record, agent_run_id)
    session.add(llm_call)
    session.flush()

    logger.debug(
        f"Created LLM call: id={llm_call.id}, model={call_record.model_alias}, "
        f"agent_run_id={agent_run_id}"
    )

    return llm_call


def _update_conversation_totals(session: Session, conversation_id: uuid.UUID) -> None:
    """Update conversation totals from all agent runs.

    :param session: Database session.
    :param conversation_id: The conversation ID.
    """
    conversation = get_agent_conversation_by_id(session, conversation_id)

    runs = session.query(AgentRun).filter(AgentRun.conversation_id == conversation_id).all()

    conversation.total_input_tokens = sum(r.total_input_tokens for r in runs)
    conversation.total_output_tokens = sum(r.total_output_tokens for r in runs)
    conversation.total_cache_read_tokens = sum(r.total_cache_read_tokens for r in runs)
    conversation.total_estimated_cost_usd = sum(
        (r.total_estimated_cost_usd for r in runs), Decimal("0")
    )

    session.flush()


def get_agent_run_with_calls(
    session: Session,
    agent_run_id: uuid.UUID,
) -> AgentRun:
    """Get an agent run with all LLM calls loaded.

    :param session: Database session.
    :param agent_run_id: The agent run ID.
    :returns: The agent run with llm_calls relationship loaded.
    """
    return (
        session.query(AgentRun)
        .options(joinedload(AgentRun.llm_calls))
        .filter(AgentRun.id == agent_run_id)
        .one()
    )
