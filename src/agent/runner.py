"""Agent runner for executing tool-based LLM workflows."""

from __future__ import annotations

import concurrent.futures
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from src.agent.bedrock_client import BedrockClient, ToolUseBlock
from src.agent.enums import ConfidenceLevel, ConfirmationType, RiskLevel, ToolDecisionType
from src.agent.exceptions import (
    BedrockClientError,
    BedrockResponseError,
    MaxStepsExceededError,
    ToolExecutionError,
    ToolTimeoutError,
)
from src.agent.models import (
    AgentRunResult,
    ConfirmationRequest,
    ConversationState,
    PendingConfirmation,
    PendingToolAction,
    ToolCall,
    ToolDef,
)
from src.agent.utils.call_tracking import TrackingContext, set_tracking_context
from src.agent.utils.confidence_classifier import classify_action_confidence
from src.agent.utils.config import DEFAULT_AGENT_CONFIG, AgentConfig
from src.agent.utils.confirmation_classifier import (
    ClassificationParseError,
    ToolDecision,
    apply_correction,
    classify_batch_confirmation_response,
)
from src.agent.utils.context_manager import (
    append_messages,
    apply_sliding_window,
    build_context_messages,
    clear_pending_confirmation,
    load_conversation_state,
    save_conversation_state,
    set_pending_confirmation,
)
from src.agent.utils.formatting import format_action
from src.agent.utils.memory import build_memory_context
from src.agent.utils.tools.registry import ToolRegistry
from src.agent.utils.tools.selector import ToolSelector
from src.database.agent_tracking import (
    complete_agent_run,
    create_agent_conversation,
    create_agent_run,
    get_agent_conversation_by_id,
)
from src.database.memory import get_active_memories

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import (
        ToolConfigurationTypeDef,
    )
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

# System prompt (fully static for caching - no dynamic content)
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools for managing tasks, goals, reading lists, ideas, and reminders.

## Your Capabilities

You can work with:
- **Tasks**: Query, get, create, and update tasks (including changing due dates, status, priority)
- **Goals**: Query, get, create, and update goals
- **Reading List**: Query, get, create, and update reading list items
- **Ideas**: Query, get, create, and update ideas
- **Reminders**: Create, query, update, and cancel reminders (one-time or recurring)
- **Memory**: Store and update important information for future conversations

## Dynamic Tool Selection

Your available tools are dynamically selected based on the conversation context. Tools are organised into domains (e.g., tasks, goals, reminders). When you discuss a topic, all tools for that domain become available.

Key behaviours:
- When you switch topics, your available tools will change to match the new domain
- If the conversation spans multiple domains, tools from the most recent domains are prioritised
- To manage tool limits, older domains may be dropped when you start discussing new topics
- You can always bring back a domain by mentioning it again

The tools currently available to you reflect what the system thinks you need based on the conversation so far. If a tool you expect is missing, the user may need to mention that topic more explicitly.

## Guidelines

When using tools:
1. Analyse the user's request carefully
2. Use the most appropriate tool for the task
3. If a query returns no results, inform the user rather than guessing
4. For updates or creates, confirm what was done after completion
5. Handle errors gracefully and explain any issues to the user
6. When users mention relative dates (e.g., "end of week", "next Friday"), calculate the actual date
7. Before calling create tools, check if the name/title is specific enough to find later. If vague (e.g., "Send email", "Meeting"), nudge the user for more details

IMPORTANT: Before saying you cannot do something, check your available tools. If you have a tool that could accomplish the task, use it.

## Memory Management

You have persistent memory across conversations. Store facts about people, user preferences, and recurring context - but not transient details.

**Be proactive about memory.** When the user shares useful information, store it immediately and briefly confirm what you've remembered. Don't ask for permission first - just store it and inform them.

Examples of what to proactively remember:
- People: "My manager is Sarah", "I'm meeting John tomorrow" → store the person and their relationship
- Preferences: "I prefer morning meetings", "I use British English" → store the preference
- Context: "I'm working on the Q2 launch", "I have a dentist appointment Friday" → store ongoing context
- Projects: "The API migration is my top priority" → store project context

When you store something proactively, briefly acknowledge it (e.g., "I've noted that Sarah is your manager" or "Remembered - you prefer morning meetings"). Keep acknowledgements short and natural.

**Explicit requests:** If the user explicitly asks you to remember something (e.g., "remember that...", "add to memory..."), store it immediately.

**Updating memories:** Use update_memory with the memory ID shown as [id:xxxxxxxx] when information changes.

## Response Formatting

You can use Markdown formatting in your responses. The following formats are supported:
- **bold** for emphasis or important items
- *italic* for subtle emphasis
- ~~strikethrough~~ for removed or cancelled items
- __underline__ for additional emphasis
- [text](url) for links
- ## Headers for section titles

Use formatting sparingly to improve readability. Don't over-format simple responses.

Always be concise and helpful in your responses. Keep responses short and to the point. Use British English spelling and vocabulary (e.g., "colour" not "color", "organised" not "organized")."""


@dataclass
class _RunState:
    """Mutable state for an agent run."""

    messages: list[dict[str, Any]]
    tool_calls: list[ToolCall]
    steps_taken: int
    tools: dict[str, ToolDef]
    context_length: int = 0  # Number of messages from conversation context


@dataclass
class _ToolUseContext:
    """Context for processing a tool use request."""

    tool_use_id: str
    tool_name: str
    input_args: dict[str, Any]


@dataclass
class _ResolvedTools:
    """Result of resolving tools for a run."""

    tool_names: list[str]
    domains: list[str]


class AgentRunner:
    """Executes the reasoning and tool-calling loop.

    The AgentRunner manages the conversation with the LLM and executes
    tool calls sequentially. It enforces max-step limits and handles
    HITL (Human-in-the-Loop) confirmation for sensitive tools.

    When used with a database session and conversation_id, the runner
    maintains stateful conversations with:
    - Message history preservation across runs
    - Natural language confirmation handling
    - Sliding window context management
    """

    def __init__(
        self,
        registry: ToolRegistry,
        client: BedrockClient | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        require_confirmation: bool = True,
        config: AgentConfig = DEFAULT_AGENT_CONFIG,
    ) -> None:
        """Initialise the agent runner.

        :param registry: Tool registry containing available tools.
        :param client: Bedrock client for LLM calls. Creates one if not provided.
        :param system_prompt: System prompt for the agent.
        :param require_confirmation: Whether to require confirmation for sensitive tools.
        :param config: Agent configuration. Defaults to DEFAULT_AGENT_CONFIG.
        """
        self.registry = registry
        self.client = client or BedrockClient()
        self._base_system_prompt = system_prompt
        self.require_confirmation = require_confirmation
        self._config = config

        # Run-scoped system prompt (set at start of each run, includes memory context)
        self._run_system_prompt: str = ""

        # Executor for tool timeout handling (single worker for sequential execution)
        self._tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        logger.debug(
            f"Agent configured: selector={self._config.selector_model}, "
            f"chat={self._config.chat_model}, max_steps={self._config.max_steps}, "
            f"tool_timeout={self._config.tool_timeout_seconds}s"
        )

        # Create internal tool selector
        self._selector = ToolSelector(registry=registry, client=self.client)

    def _build_system_prompt(self, session: Session) -> None:
        """Build and store the run-scoped system prompt with memory context.

        Loads active memories from the database and appends them to the base
        system prompt. Memory ordering is deterministic for prompt caching.
        The result is stored in `_run_system_prompt` for access during the run.

        :param session: Database session.
        """
        memories = get_active_memories(session)
        memory_context = build_memory_context(memories)

        if memory_context:
            self._run_system_prompt = f"{self._base_system_prompt}\n\n{memory_context}"
        else:
            self._run_system_prompt = self._base_system_prompt

    def run(
        self,
        user_message: str,
        session: Session,
        conversation_id: uuid.UUID | None = None,
        tool_names: list[str] | None = None,
        tracking_context: TrackingContext | None = None,
    ) -> AgentRunResult:
        """Execute the agent with the given user message and tools.

        If tool_names is not provided, the agent will automatically select
        relevant tools using the ToolSelector (with the configured selector_model).
        Standard tools are always included regardless of selection.

        The runner maintains stateful conversations with:
        - Message history preservation across runs
        - Natural language confirmation handling
        - Sliding window context management

        :param user_message: The user's input message.
        :param session: Database session for persisting state and tracking data.
        :param conversation_id: Existing conversation ID to continue. If not
            provided, a new conversation is created.
        :param tool_names: Optional list of tool names. If None, auto-selects.
        :param tracking_context: Tracking context for recording LLM calls. If not
            provided, a new context is created automatically.
        :returns: Result of the agent run.
        :raises MaxStepsExceededError: If the agent exceeds max_steps.
        :raises BedrockClientError: If the Bedrock API call fails.
        :raises ToolNotFoundError: If a requested tool is not found.
        """
        # Load or create conversation state
        if conversation_id is not None:
            conversation = get_agent_conversation_by_id(session, conversation_id)
            conv_state = load_conversation_state(conversation)
            db_conversation_id = conversation_id
        else:
            conversation = create_agent_conversation(session)
            db_conversation_id = conversation.id
            conv_state = ConversationState(conversation_id=db_conversation_id)

        # Build system prompt with memory context (loaded once per run)
        self._build_system_prompt(session)

        agent_run = create_agent_run(
            session, conversation_id=db_conversation_id, user_message=user_message
        )
        db_agent_run_id = agent_run.id

        # Always track - create context if not provided
        if tracking_context is None:
            tracking_context = TrackingContext(
                run_id=db_agent_run_id,
                conversation_id=db_conversation_id,
            )

        set_tracking_context(tracking_context)

        try:
            # Check for pending confirmation
            if conv_state.pending_confirmation is not None:
                result = self._handle_confirmation_response(
                    user_message=user_message,
                    conv_state=conv_state,
                )
            else:
                # Normal execution flow
                result = self._execute_run(
                    user_message=user_message,
                    tool_names=tool_names,
                    conv_state=conv_state,
                )

            # Apply sliding window if needed
            apply_sliding_window(conv_state, self.client)

            # Save updated state
            save_conversation_state(session, conversation, conv_state)

            # Persist tracking data
            complete_agent_run(
                session,
                agent_run_id=db_agent_run_id,
                tracking_context=tracking_context,
                final_response=result.response,
                stop_reason=result.stop_reason,
                steps_taken=result.steps_taken,
            )

            return result
        finally:
            set_tracking_context(None)

    def _handle_confirmation_response(
        self,
        user_message: str,
        conv_state: ConversationState,
    ) -> AgentRunResult:
        """Handle a user response when there's a pending confirmation.

        Classifies the user's message as CONFIRM, DENY, PARTIAL_CONFIRM,
        or NEW_INTENT and processes accordingly.

        :param user_message: The user's response message.
        :param conv_state: Conversation state with pending confirmation.
        :returns: Result of handling the confirmation.
        """
        pending = conv_state.pending_confirmation
        if pending is None:
            # Should not happen, but handle gracefully
            return self._execute_run(user_message, None, conv_state)

        # Classify the user's response using batch classifier
        try:
            result = classify_batch_confirmation_response(
                client=self.client,
                user_message=user_message,
                pending=pending,
            )
        except ClassificationParseError as e:
            logger.error(
                f"Failed to classify confirmation response: {e}, "
                f"conversation_id={conv_state.conversation_id}"
            )
            # Clear pending and return error to user
            clear_pending_confirmation(conv_state)

            return AgentRunResult(
                response="Sorry, I didn't quite catch that - could you clarify?",
                tool_calls=[],
                steps_taken=0,
                stop_reason="classification_error",
            )

        logger.info(f"Confirmation response classified as: {result.classification}")

        if result.classification == ConfirmationType.CONFIRM:
            # Clear pending and execute all tools
            clear_pending_confirmation(conv_state)

            tool_count = len(pending.tools)
            logger.info(f"User confirmed all {tool_count} action(s)")

            return self._execute_confirmed_tools(
                pending=pending,
                conv_state=conv_state,
                user_message=user_message,
            )

        if result.classification == ConfirmationType.DENY:
            # Clear pending and return cancellation
            clear_pending_confirmation(conv_state)

            # Add user message to context
            append_messages(conv_state, [self.client.create_user_message(user_message)])

            logger.info("User declined all confirmations")

            return AgentRunResult(
                response="No worries, I won't make those changes.",
                tool_calls=[],
                steps_taken=0,
                stop_reason="user_cancelled",
            )

        if result.classification == ConfirmationType.PARTIAL_CONFIRM:
            # Handle partial confirmation with per-tool decisions
            logger.info(
                f"User provided partial confirmation: {len(result.tool_decisions)} decisions"
            )

            return self._handle_partial_confirmation(
                pending=pending,
                conv_state=conv_state,
                user_message=user_message,
                tool_decisions=result.tool_decisions,
            )

        # NEW_INTENT
        # Clear pending and process as new request
        clear_pending_confirmation(conv_state)

        logger.info("User provided new intent, processing as new request")

        return self._execute_run(
            user_message=user_message,
            tool_names=None,  # Force tool re-selection for new intent
            conv_state=conv_state,
        )

    def _execute_confirmed_tools(
        self,
        pending: PendingConfirmation,
        conv_state: ConversationState,
        user_message: str,
        tools_to_execute: list[PendingToolAction] | None = None,
    ) -> AgentRunResult:
        """Execute confirmed tools from a batch confirmation.

        Directly executes the tools with saved arguments, then hands off to
        the agent loop to generate a response. The user's confirmation message
        is included so the LLM can see any additional requests.

        :param pending: The confirmed pending action with tool details.
        :param conv_state: Conversation state for context.
        :param user_message: The user's confirmation message (may contain followup).
        :param tools_to_execute: Specific tools to execute. If None, executes all.
        :returns: Result of the agent run.
        """
        tools = tools_to_execute if tools_to_execute is not None else pending.tools

        if not tools:
            # No tools to execute (edge case)
            return AgentRunResult(
                response="Nothing to do here.",
                tool_calls=[],
                steps_taken=0,
                stop_reason="no_actions",
            )

        # Build messages: context + user confirmation + assistant tool requests + tool results
        context_messages = build_context_messages(conv_state)
        context_length = len(context_messages)
        user_confirmation_msg = self.client.create_user_message(user_message)

        # Build assistant message with all tool_use blocks
        tool_use_contents: list[dict[str, Any]] = []
        for tool_action in tools:
            tool_use_contents.append(
                {
                    "toolUse": {
                        "toolUseId": tool_action.tool_use_id,
                        "name": tool_action.tool_name,
                        "input": tool_action.input_args,
                    }
                }
            )

        assistant_tool_request: dict[str, Any] = {
            "role": "assistant",
            "content": tool_use_contents,
        }

        # Execute all tools and collect results
        tool_calls: list[ToolCall] = []
        tool_result_contents: list[dict[str, Any]] = []

        for tool_action in tools:
            tool = self.registry.get(tool_action.tool_name)
            tool_result, tool_call = self._execute_and_create_tool_call(
                tool=tool,
                tool_use_id=tool_action.tool_use_id,
                input_args=tool_action.input_args,
            )
            tool_calls.append(tool_call)

            logger.info(
                f"Confirmed tool executed: tool={tool_action.tool_name}, error={tool_call.is_error}"
            )

            tool_result_contents.append(
                self._build_tool_result_block(
                    tool_action.tool_use_id, tool_result, tool_call.is_error
                )
            )

        tool_result_msg: dict[str, Any] = {"role": "user", "content": tool_result_contents}

        messages: list[Any] = [
            *context_messages,
            user_confirmation_msg,
            assistant_tool_request,
            tool_result_msg,
        ]

        # Build tool config and state, then hand off to agent loop
        tool_names = pending.selected_tools or []

        state = _RunState(
            messages=messages,
            tool_calls=tool_calls,
            steps_taken=1,
            tools=self._build_tools_dict(tool_names),
            context_length=context_length,
        )

        # Use domains from conv_state for incremental tool caching
        domains = conv_state.selected_domains if conv_state else []
        return self._run_agent_loop(
            state,
            self._build_tool_config(domains),
            conv_state,
        )

    def _handle_partial_confirmation(
        self,
        pending: PendingConfirmation,
        conv_state: ConversationState,
        user_message: str,
        tool_decisions: list[ToolDecision],
    ) -> AgentRunResult:
        """Handle a partial confirmation with per-tool decisions.

        :param pending: The pending confirmation with list of tools.
        :param conv_state: Conversation state for context.
        :param user_message: The user's response message.
        :param tool_decisions: Per-tool decisions from the classifier.
        :returns: Result of the agent run.
        """
        clear_pending_confirmation(conv_state)

        # Build decision map for quick lookup
        decision_map: dict[int, ToolDecision] = {d.index: d for d in tool_decisions}

        # Process each tool based on its decision
        tools_to_execute: list[PendingToolAction] = []
        rejected_count = 0

        for tool_action in pending.tools:
            decision = decision_map.get(tool_action.index)

            if decision is None:
                # No explicit decision - default to approve
                tools_to_execute.append(tool_action)
                continue

            if decision.decision == ToolDecisionType.APPROVE:
                tools_to_execute.append(tool_action)

            elif decision.decision == ToolDecisionType.REJECT:
                rejected_count += 1
                logger.info(f"Tool rejected by user: {tool_action.tool_name}")

            elif decision.decision == ToolDecisionType.MODIFY and decision.correction:
                try:
                    updated_args = apply_correction(
                        client=self.client,
                        tool=tool_action,
                        correction=decision.correction,
                    )
                    # Create modified tool action
                    modified_action = PendingToolAction(
                        index=tool_action.index,
                        tool_use_id=tool_action.tool_use_id,
                        tool_name=tool_action.tool_name,
                        tool_description=tool_action.tool_description,
                        input_args=updated_args,
                        action_summary=self._generate_action_summary(
                            tool_action.tool_description, updated_args
                        ),
                    )
                    tools_to_execute.append(modified_action)
                    logger.info(
                        f"Tool modified: {tool_action.tool_name}, "
                        f"correction='{decision.correction}'"
                    )
                except ClassificationParseError as e:
                    logger.warning(f"Failed to apply correction to {tool_action.tool_name}: {e}")
                    # Add error message to response
                    append_messages(conv_state, [self.client.create_user_message(user_message)])
                    return AgentRunResult(
                        response=(
                            f"I couldn't apply your correction to the "
                            f"'{tool_action.tool_name}' action. Please try rephrasing "
                            f"or provide more specific instructions."
                        ),
                        tool_calls=[],
                        steps_taken=0,
                        stop_reason="correction_error",
                    )

        if not tools_to_execute:
            # All tools rejected
            append_messages(conv_state, [self.client.create_user_message(user_message)])
            return AgentRunResult(
                response="Got it, I'll leave everything as is.",
                tool_calls=[],
                steps_taken=0,
                stop_reason="user_cancelled",
            )

        logger.info(
            f"Executing {len(tools_to_execute)} tool(s) after partial confirmation "
            f"({rejected_count} rejected)"
        )

        return self._execute_confirmed_tools(
            pending=pending,
            conv_state=conv_state,
            user_message=user_message,
            tools_to_execute=tools_to_execute,
        )

    def _resolve_tools(
        self,
        user_message: str,
        tool_names: list[str] | None,
        conv_state: ConversationState | None,
    ) -> _ResolvedTools:
        """Resolve the tools to use for this run.

        Uses context-aware tool selection:
        - First turn: Full selection based on user message
        - Subsequent turns: Additive mode - only adds tools if needed

        This prevents losing relevant tools when the user provides clarifying
        details (e.g., "both work and due 1st jan" after asking to create tasks).

        :param user_message: User message for auto-selection.
        :param tool_names: Explicit tool names override.
        :param conv_state: Conversation state with previous tool selection.
        :returns: ResolvedTools with tool names and domains.
        """
        if tool_names is not None:
            # Explicit tools - extract domains from them
            domains = self._selector._tools_to_domains(tool_names)
            return _ResolvedTools(tool_names=tool_names, domains=domains)

        # Get current domains from conversation state (if any)
        current_domains = (
            conv_state.selected_domains
            if conv_state is not None and conv_state.selected_domains
            else None
        )

        # Select tools - additive mode if we have current domains
        selection = self._selector.select(
            user_message,
            model=self._config.selector_model,
            current_domains=current_domains,
        )

        if current_domains:
            # Selector already handles merging and pruning - use its result directly
            if selection.tool_names:
                logger.info(
                    f"Tool selection: {selection.tool_names}, "
                    f"domains={selection.domains}, reasoning={selection.reasoning}"
                )
                return _ResolvedTools(tool_names=selection.tool_names, domains=selection.domains)
            # No domains selected - keep current tools unchanged
            prev_tools = conv_state.selected_tools if conv_state else []
            logger.debug(f"No domains selected, keeping: {prev_tools}")
            return _ResolvedTools(tool_names=prev_tools, domains=current_domains)
        # First turn: use full selection
        logger.info(
            f"Initial tool selection: {selection.tool_names}, reasoning={selection.reasoning}"
        )
        return _ResolvedTools(tool_names=selection.tool_names, domains=selection.domains)

    def _build_initial_messages(
        self,
        user_message: str,
        conv_state: ConversationState | None,
        domain_notification: str | None = None,
    ) -> tuple[list[Any], int]:
        """Build initial messages for the agent run.

        Dynamic context (current datetime, domain changes) is injected here rather
        than in the system prompt to keep the system prompt fully static and cacheable.

        :param user_message: The user's input message.
        :param conv_state: Optional conversation state for context.
        :param domain_notification: Optional notification about domain changes.
        :returns: Tuple of (messages, context_length) where context_length is
            the number of messages from conversation history.
        """
        # Build dynamic context prefix (keeps system prompt static for caching)
        current_time = datetime.now().strftime("%A, %Y-%m-%d %H:%M %Z").strip()
        context_parts = [f"[Current time: {current_time}]"]
        if domain_notification:
            context_parts.append(domain_notification)

        context_prefix = "\n".join(context_parts)
        effective_message = f"{context_prefix}\n\n{user_message}"

        if conv_state is not None:
            context_messages = build_context_messages(conv_state)
            new_user_message = self.client.create_user_message(effective_message)
            return [*context_messages, new_user_message], len(context_messages)
        return [self.client.create_user_message(effective_message)], 0

    def _build_tool_config(
        self,
        domains: list[str],
    ) -> ToolConfigurationTypeDef:
        """Build Bedrock tool configuration from domains.

        Uses domain-based caching with cache points after each domain's tools.
        System tools are always included automatically.

        :param domains: Ordered domain list for cache point placement.
        :returns: Tool configuration (always includes at least system tools).
        """
        return cast(
            "ToolConfigurationTypeDef",
            self.registry.to_bedrock_tool_config_with_cache_points(domains),
        )

    def _build_tools_dict(self, tool_names: list[str]) -> dict[str, ToolDef]:
        """Build a dictionary of tools by name.

        :param tool_names: List of tool names to include.
        :returns: Dictionary mapping tool names to definitions.
        """
        if not tool_names:
            return {}
        return {t.name: t for t in self.registry.get_many(tool_names)}

    def _execute_and_create_tool_call(
        self,
        tool: ToolDef,
        tool_use_id: str,
        input_args: dict[str, Any],
    ) -> tuple[dict[str, Any], ToolCall]:
        """Execute a tool and create a ToolCall record.

        :param tool: Tool definition to execute.
        :param tool_use_id: Unique ID for this tool use.
        :param input_args: Arguments for the tool.
        :returns: Tuple of (tool_result, ToolCall record).
        """
        try:
            tool_result = self._execute_tool(tool, input_args)
            is_error = False
        except ToolTimeoutError as e:
            logger.warning(f"Tool execution timed out: {e}")
            tool_result = {
                "error": str(e),
                "error_type": "timeout",
                "suggestion": "The operation took too long. Try a simpler query or different approach.",
            }
            is_error = True
        except ToolExecutionError as e:
            logger.warning(f"Tool execution failed: {e}")
            tool_result = {"error": e.error, "error_type": "execution"}
            is_error = True

        tool_call = ToolCall(
            tool_use_id=tool_use_id,
            tool_name=tool.name,
            input_args=input_args,
            output=tool_result,
            is_error=is_error,
        )

        return tool_result, tool_call

    def _execute_run(
        self,
        user_message: str,
        tool_names: list[str] | None,
        conv_state: ConversationState | None,
    ) -> AgentRunResult:
        """Execute the agent run logic.

        :param user_message: The user's input message.
        :param tool_names: Optional list of tool names. If None, auto-selects.
        :param conv_state: Optional conversation state for context.
        :returns: Result of the agent run.
        """
        resolved = self._resolve_tools(user_message, tool_names, conv_state)

        # Check for domain changes and build notification
        domain_notification = self._build_domain_change_notification(conv_state, resolved.domains)

        # Update conversation state with selected tools and domains
        if conv_state is not None:
            conv_state.selected_tools = resolved.tool_names
            conv_state.selected_domains = resolved.domains

        # Build tool config (includes system tools automatically) and tools dict
        tool_config = self._build_tool_config(resolved.domains)
        initial_messages, context_length = self._build_initial_messages(
            user_message, conv_state, domain_notification
        )

        # Build tools dict including system tools for execution lookup
        system_tools = [t.name for t in self.registry.get_system_tools()]
        all_tool_names = list(dict.fromkeys(system_tools + resolved.tool_names))

        state = _RunState(
            messages=initial_messages,
            tool_calls=[],
            steps_taken=0,
            tools=self._build_tools_dict(all_tool_names),
            context_length=context_length,
        )

        logger.info(
            f"Starting agent run: tools={list(state.tools.keys()) or '(none)'}, "
            f"domains={resolved.domains}, max_steps={self._config.max_steps}"
        )

        return self._run_agent_loop(state, tool_config, conv_state)

    def _build_domain_change_notification(
        self,
        conv_state: ConversationState | None,
        new_domains: list[str],
    ) -> str | None:
        """Build a notification message about domain changes.

        :param conv_state: Conversation state with previous domains.
        :param new_domains: Newly selected domains.
        :returns: Notification message or None if no changes.
        """
        if conv_state is None or not conv_state.selected_domains:
            # First turn - no change notification needed
            return None

        prev_set = set(conv_state.selected_domains)
        new_set = set(new_domains)

        added = new_set - prev_set
        removed = prev_set - new_set

        if not added and not removed:
            return None

        # Build human-readable domain names (strip 'domain:' prefix)
        def format_domains(domains: set[str]) -> str:
            return ", ".join(d.replace("domain:", "") for d in sorted(domains))

        parts: list[str] = []
        if added:
            parts.append(f"Added domains: {format_domains(added)}")
        if removed:
            parts.append(f"Removed domains: {format_domains(removed)}")

        notification = f"[Tool update: {'; '.join(parts)}]"
        logger.info(f"Domain change notification: {notification}")
        return notification

    def _run_agent_loop(
        self,
        state: _RunState,
        tool_config: ToolConfigurationTypeDef | None,
        conv_state: ConversationState | None,
    ) -> AgentRunResult:
        """Execute the main agent reasoning loop.

        :param state: Mutable run state.
        :param tool_config: Tool configuration for Bedrock.
        :param conv_state: Conversation state for persistence.
        :returns: Result of the agent run.
        """
        while True:
            if state.steps_taken >= self._config.max_steps:
                logger.warning(f"Agent exceeded max steps: max={self._config.max_steps}")
                raise MaxStepsExceededError(self._config.max_steps, state.steps_taken)

            response = self._call_llm(state.messages, tool_config)
            stop_reason = self.client.get_stop_reason(response)
            logger.debug(f"Agent step {state.steps_taken}: stop_reason={stop_reason}")

            if stop_reason == "tool_use":
                result = self._handle_tool_use(response, state, conv_state)
                if result is not None:
                    return result
                state.steps_taken += 1
            elif stop_reason == "end_turn":
                return self._build_final_result(response, state, "end_turn", conv_state)
            elif stop_reason == "max_tokens":
                return self._handle_max_tokens(state, conv_state)
            else:
                logger.warning(f"Unexpected stop reason: {stop_reason}")
                return self._build_final_result(response, state, stop_reason, conv_state)

    def _handle_max_tokens(
        self,
        state: _RunState,
        conv_state: ConversationState | None,
    ) -> AgentRunResult:
        """Handle when the LLM response was truncated due to max_tokens limit.

        This occurs when the model tries to generate more content (typically
        multiple tool calls) than the max_tokens limit allows. Rather than
        returning a partial/misleading response, we inform the user clearly.

        :param state: Current run state.
        :param conv_state: Conversation state for context.
        :returns: AgentRunResult with error message.
        """
        logger.warning(
            f"Response truncated due to max_tokens limit: "
            f"max_tokens={self._config.max_tokens}, steps={state.steps_taken}"
        )

        error_message = (
            "Your request requires more processing than I can handle in one go. "
            "Please try breaking it into smaller parts (e.g., add 3-4 items at a time)."
        )

        # Don't save partial state - the conversation is in an inconsistent state
        # The user should retry with a simpler request

        return AgentRunResult(
            response=error_message,
            tool_calls=state.tool_calls,
            steps_taken=state.steps_taken,
            stop_reason="max_tokens",
        )

    def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tool_config: ToolConfigurationTypeDef | None,
    ) -> dict[str, Any]:
        """Call the LLM and return the response.

        :param messages: Conversation messages.
        :param tool_config: Tool configuration for Bedrock.
        :returns: LLM response.
        """
        try:
            return self.client.converse(
                messages=messages,
                model_id=self._config.chat_model,
                system_prompt=self._run_system_prompt,
                tool_config=tool_config,
                max_tokens=self._config.max_tokens,
                cache_system_prompt=True,
            )
        except BedrockClientError:
            logger.exception("Bedrock API call failed during agent run")
            raise

    def _handle_tool_use(
        self,
        response: dict[str, Any],
        state: _RunState,
        conv_state: ConversationState | None,
    ) -> AgentRunResult | None:
        """Handle a tool use response from the LLM.

        When the LLM returns multiple tool uses in one response, we must
        provide a tool_result for each one. This method:
        1. Executes safe tools immediately
        2. Collects all sensitive tools for batch confirmation

        :returns: AgentRunResult if the run should stop, None to continue.
        """
        try:
            tool_uses = self.client.parse_tool_use(response)
        except BedrockResponseError as e:
            logger.error(f"Invalid Bedrock response: {e}")
            return AgentRunResult(
                response=f"Received invalid response from AI: {e}",
                tool_calls=state.tool_calls,
                steps_taken=state.steps_taken,
                stop_reason="error",
            )

        if not tool_uses:
            logger.warning("stop_reason is tool_use but no tool uses found")
            return AgentRunResult(
                response="",
                tool_calls=state.tool_calls,
                steps_taken=state.steps_taken,
                stop_reason="unknown",
            )

        # Build contexts for all tool uses
        contexts: list[_ToolUseContext] = []
        for tool_use in tool_uses:
            ctx = _ToolUseContext(
                tool_use_id=tool_use.id,
                tool_name=tool_use.name,
                input_args=tool_use.input,
            )
            contexts.append(ctx)
            logger.info(f"Tool use requested: tool={ctx.tool_name}, id={ctx.tool_use_id}")

        # Check if ANY tool is unknown - if so, error all
        unknown_tools = [ctx for ctx in contexts if ctx.tool_name not in state.tools]
        if unknown_tools:
            self._handle_unknown_tool(tool_uses, state, response)
            return None

        # Separate tools into safe and sensitive
        safe_contexts: list[_ToolUseContext] = []
        sensitive_contexts: list[_ToolUseContext] = []

        for ctx in contexts:
            tool = state.tools[ctx.tool_name]
            if self.require_confirmation and tool.risk_level == RiskLevel.SENSITIVE:
                sensitive_contexts.append(ctx)
            else:
                safe_contexts.append(ctx)

        # If there are sensitive tools requiring confirmation, create batch request
        if sensitive_contexts:
            logger.info(
                f"Batch confirmation needed: {len(sensitive_contexts)} sensitive, "
                f"{len(safe_contexts)} safe"
            )
            return self._request_batch_confirmation(
                sensitive_contexts=sensitive_contexts,
                safe_contexts=safe_contexts,
                state=state,
                conv_state=conv_state,
                response=response,
            )

        # No sensitive tools - execute all tools
        self._execute_all_tools(contexts, state, response)
        return None

    def _execute_all_tools(
        self,
        contexts: list[_ToolUseContext],
        state: _RunState,
        response: dict[str, Any],
    ) -> None:
        """Execute all tools in the response and record results.

        All tool results must be in a SINGLE user message with multiple
        toolResult blocks. Bedrock requires this format when the assistant
        returned multiple tool_use blocks.

        :param contexts: List of tool use contexts to execute.
        :param state: Current run state.
        :param response: Full LLM response (for the assistant message).
        """
        # Add the assistant message once (contains all tool_use blocks)
        state.messages.append(response["output"]["message"])

        # Execute all tools and collect results
        tool_result_contents: list[dict[str, Any]] = []
        for ctx in contexts:
            tool = state.tools[ctx.tool_name]
            tool_result, tool_call = self._execute_and_create_tool_call(
                tool=tool,
                tool_use_id=ctx.tool_use_id,
                input_args=ctx.input_args,
            )
            state.tool_calls.append(tool_call)
            tool_result_contents.append(
                self._build_tool_result_block(ctx.tool_use_id, tool_result, tool_call.is_error)
            )

        # Add single message with ALL tool results
        state.messages.append({"role": "user", "content": tool_result_contents})

    def _handle_unknown_tool(
        self,
        tool_uses: list[ToolUseBlock],
        state: _RunState,
        response: dict[str, Any],
    ) -> None:
        """Handle unknown tool(s) in the response.

        When the LLM returns multiple tool uses in one response and any is
        unknown, we must provide error results for ALL of them due to Bedrock
        API requirements (every tool_use must have a corresponding tool_result).

        All tool results must be in a SINGLE user message with multiple
        toolResult blocks.

        :param tool_uses: All tool uses from the response.
        :param state: Current run state.
        :param response: Full LLM response.
        """
        state.messages.append(response["output"]["message"])

        # Collect all error results
        tool_result_contents: list[dict[str, Any]] = []
        for tool_use in tool_uses:
            tool_use_id = tool_use.id
            tool_name = tool_use.name
            input_args = tool_use.input

            if tool_name not in state.tools:
                logger.error(f"LLM requested unknown tool: {tool_name}")
                error_result = {
                    "error": f"Unknown tool: {tool_name}",
                    "error_type": "validation",
                }
            else:
                # Tool exists but we can't execute it because another tool
                # in this batch is unknown - we need to bail out entirely
                logger.warning(f"Skipping tool {tool_name} due to unknown tool in same request")
                error_result = {
                    "error": "Execution skipped due to unknown tool in batch",
                    "error_type": "execution",
                }

            state.tool_calls.append(
                ToolCall(
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                    input_args=input_args,
                    output=error_result,
                    is_error=True,
                )
            )
            tool_result_contents.append(
                self._build_tool_result_block(tool_use_id, error_result, is_error=True)
            )

        # Add single message with ALL tool results
        state.messages.append({"role": "user", "content": tool_result_contents})

    def _request_batch_confirmation(
        self,
        sensitive_contexts: list[_ToolUseContext],
        safe_contexts: list[_ToolUseContext],
        state: _RunState,
        conv_state: ConversationState | None,
        response: dict[str, Any],
    ) -> AgentRunResult | None:
        """Create a batch confirmation request for multiple sensitive tools.

        Uses confidence classification to determine if confirmation is needed:
        - EXPLICIT: User directly requested this action - execute immediately
        - NEEDS_CONFIRMATION: Agent inferred or suggested - request confirmation

        Safe tools are executed immediately. Sensitive tools are either executed
        (if EXPLICIT) or collected into a batch confirmation request.

        :param sensitive_contexts: Contexts for sensitive tools needing confirmation.
        :param safe_contexts: Contexts for safe tools to execute immediately.
        :param state: Current run state.
        :param conv_state: Conversation state for persistence.
        :param response: Full LLM response.
        :returns: AgentRunResult with batch confirmation request, or None if
            all tools were executed (EXPLICIT confidence).
        """
        # Classify confidence for the sensitive tools
        # Build a combined action description for classification
        action_descriptions = []
        for ctx in sensitive_contexts:
            tool = state.tools[ctx.tool_name]
            # Try to extract entity name from args for better description
            entity_name = self._extract_entity_name(ctx.input_args)
            action_desc = format_action(ctx.tool_name, entity_name, ctx.input_args)
            action_descriptions.append(action_desc)

        combined_action = "; ".join(action_descriptions)

        classification = classify_action_confidence(
            client=self.client,
            messages=state.messages,
            proposed_action=combined_action,
        )

        logger.info(
            f"Confidence classification: level={classification.level}, "
            f"reasoning='{classification.reasoning[:80]}...'"
        )

        if classification.level == ConfidenceLevel.EXPLICIT:
            # User explicitly requested this - execute without confirmation
            logger.info(
                f"EXPLICIT confidence - executing {len(sensitive_contexts)} sensitive "
                f"tool(s) without confirmation"
            )
            # Combine all contexts and execute
            all_contexts = safe_contexts + sensitive_contexts
            self._execute_all_tools(all_contexts, state, response)
            return None  # Continue agent loop

        # NEEDS_CONFIRMATION - proceed with confirmation request
        logger.info(
            f"NEEDS_CONFIRMATION - requesting confirmation for {len(sensitive_contexts)} "
            f"sensitive tool(s)"
        )

        # Execute safe tools first (if any)
        if safe_contexts:
            logger.info(f"Executing {len(safe_contexts)} safe tool(s) before confirmation")
            # Add the assistant message (contains all tool_use blocks)
            state.messages.append(response["output"]["message"])

            # Execute safe tools and collect results
            tool_result_contents: list[dict[str, Any]] = []
            for ctx in safe_contexts:
                tool = state.tools[ctx.tool_name]
                tool_result, tool_call = self._execute_and_create_tool_call(
                    tool=tool,
                    tool_use_id=ctx.tool_use_id,
                    input_args=ctx.input_args,
                )
                state.tool_calls.append(tool_call)
                tool_result_contents.append(
                    self._build_tool_result_block(ctx.tool_use_id, tool_result, tool_call.is_error)
                )

            # Add placeholder results for sensitive tools (we'll execute them after confirmation)
            for ctx in sensitive_contexts:
                tool_result_contents.append(
                    self._build_tool_result_block(
                        ctx.tool_use_id, {"status": "awaiting_confirmation"}
                    )
                )

            # Add single message with ALL tool results
            state.messages.append({"role": "user", "content": tool_result_contents})

        # Build pending tool actions with 1-based indices
        pending_tools: list[PendingToolAction] = []
        for idx, ctx in enumerate(sensitive_contexts, start=1):
            tool = state.tools[ctx.tool_name]
            action_summary = self._generate_action_summary(tool.description, ctx.input_args)

            # Fetch current entity to get previous values for diff display
            previous_values = self._fetch_previous_values(tool, ctx.input_args, state.tools)
            entity_name = previous_values.pop("_entity_name", None) or self._extract_entity_name(
                ctx.input_args
            )

            pending_tools.append(
                PendingToolAction(
                    index=idx,
                    tool_use_id=ctx.tool_use_id,
                    tool_name=ctx.tool_name,
                    tool_description=tool.description,
                    input_args=ctx.input_args,
                    action_summary=action_summary,
                    previous_values=previous_values,
                    entity_name=entity_name,
                )
            )

        # Store pending confirmation in conversation state
        if conv_state is not None:
            pending = PendingConfirmation(
                tools=pending_tools,
                selected_tools=list(state.tools.keys()),
            )
            set_pending_confirmation(conv_state, pending)

            # Save current messages to state for resumption
            new_messages = state.messages[state.context_length :]
            append_messages(conv_state, new_messages)

        logger.info(
            f"Batch confirmation requested: {len(pending_tools)} tool(s) "
            f"({len(safe_contexts)} safe already executed)"
        )

        return AgentRunResult(
            response="",
            tool_calls=state.tool_calls,
            steps_taken=state.steps_taken,
            stop_reason="confirmation_required",
            confirmation_request=ConfirmationRequest(tools=pending_tools),
        )

    def _build_final_result(
        self,
        response: dict[str, Any],
        state: _RunState,
        stop_reason: str,
        conv_state: ConversationState | None,
    ) -> AgentRunResult:
        """Build the final result when the agent is done."""
        final_response = self.client.parse_text_response(response)

        # Update conversation state with messages from this run
        if conv_state is not None:
            # Add the final assistant message
            state.messages.append(response["output"]["message"])
            # Only append new messages (skip context that's already stored)
            new_messages = state.messages[state.context_length :]
            append_messages(conv_state, new_messages)

        if stop_reason == "end_turn":
            logger.info(
                f"Agent run completed: steps={state.steps_taken}, "
                f"tool_calls={len(state.tool_calls)}"
            )
        return AgentRunResult(
            response=final_response,
            tool_calls=state.tool_calls,
            steps_taken=state.steps_taken,
            stop_reason=stop_reason,
        )

    def _execute_tool(self, tool: ToolDef, input_args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with the given arguments and timeout protection.

        Uses ThreadPoolExecutor to wrap tool execution with a configurable
        timeout, preventing hung tools from blocking the agent indefinitely.

        :param tool: Tool definition to execute.
        :param input_args: Arguments for the tool.
        :returns: Tool execution result.
        :raises ToolTimeoutError: If execution exceeds configured timeout.
        :raises ToolExecutionError: If execution fails.
        """
        try:
            validated_args = tool.args_model(**input_args)
        except ValidationError as e:
            logger.warning(f"Tool argument validation failed: tool={tool.name}, error={e}")
            raise ToolExecutionError(tool.name, f"Invalid arguments: {e}") from e

        # Submit handler to executor with timeout
        future = self._tool_executor.submit(tool.handler, validated_args)
        try:
            result = future.result(timeout=self._config.tool_timeout_seconds)
            logger.debug(f"Tool executed successfully: tool={tool.name}")
            return result
        except concurrent.futures.TimeoutError:
            future.cancel()
            logger.warning(
                f"Tool execution timed out: tool={tool.name}, "
                f"timeout={self._config.tool_timeout_seconds}s"
            )
            raise ToolTimeoutError(tool.name, self._config.tool_timeout_seconds)
        except Exception as e:
            logger.exception(f"Tool execution failed: tool={tool.name}")
            raise ToolExecutionError(tool.name, str(e)) from e

    @staticmethod
    def _generate_action_summary(
        tool_description: str,
        input_args: dict[str, Any],
    ) -> str:
        """Generate a human-readable summary of a tool action.

        :param tool_description: Description of the tool.
        :param input_args: Arguments for the tool.
        :returns: Human-readable action summary.
        """
        args_display = ", ".join(f"{k}={v!r}" for k, v in input_args.items())
        return f"{tool_description}\nArguments: {args_display}"

    @staticmethod
    def _extract_entity_name(input_args: dict[str, Any]) -> str | None:
        """Extract entity name from tool arguments for display.

        Looks for common name fields in the arguments.

        :param input_args: Tool arguments.
        :returns: Entity name if found, None otherwise.
        """
        # Common name field patterns
        name_fields = ["task_name", "goal_name", "name", "title", "item_name"]
        for field in name_fields:
            if field in input_args and isinstance(input_args[field], str):
                return input_args[field]
        return None

    @staticmethod
    def _build_tool_result_block(
        tool_use_id: str,
        result: dict[str, Any],
        is_error: bool = False,
    ) -> dict[str, Any]:
        """Build a toolResult content block for Bedrock.

        :param tool_use_id: ID of the tool use being responded to.
        :param result: Result data from the tool execution.
        :param is_error: Whether the result represents an error.
        :returns: toolResult content block.
        """
        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": [{"json": result}],
                "status": "error" if is_error else "success",
            }
        }

    def _fetch_previous_values(
        self,
        tool: ToolDef,
        input_args: dict[str, Any],
        tools: dict[str, ToolDef],
    ) -> dict[str, Any]:
        """Fetch current entity values for diff display.

        For update tools, derives the get tool and fetches the current entity.
        Returns the fields being updated with their current values.

        :param tool: The update tool being called.
        :param input_args: Arguments to the update tool.
        :param tools: Available tools registry.
        :returns: Dict of current values, with '_entity_name' for display.
        """
        # Guard: only applies to update tools with id_field
        if not tool.id_field or not tool.name.startswith("update_"):
            return {}

        # Derive get tool and entity ID
        get_tool_name = tool.name.replace("update_", "get_", 1)
        get_tool = tools.get(get_tool_name)
        entity_id = input_args.get(tool.id_field)

        if not get_tool or not entity_id:
            if not get_tool:
                logger.debug(f"No get tool found for {tool.name}: {get_tool_name}")
            return {}

        try:
            # Fetch the current entity
            get_args = get_tool.args_model(**{tool.id_field: entity_id})
            result = get_tool.handler(get_args)
            entity = result.get("item", {})

            if not entity:
                return {}

            # Build previous values for fields being updated
            previous_values: dict[str, Any] = {}

            # Extract entity name for display
            name_fields = ["name", "task_name", "goal_name", "title", "item_name"]
            for name_field in name_fields:
                if name_field in entity:
                    previous_values["_entity_name"] = entity[name_field]
                    break

            # Copy current values for fields being updated
            for field in input_args:
                if field != tool.id_field and field in entity:
                    previous_values[field] = entity[field]

            logger.debug(
                f"Fetched previous values: tool={tool.name}, "
                f"entity_id={entity_id}, fields={list(previous_values.keys())}"
            )
            return previous_values

        except Exception as e:
            logger.warning(f"Failed to fetch previous values: tool={tool.name}, error={e}")
            return {}
