"""Agent runner for executing tool-based LLM workflows."""

from __future__ import annotations

import concurrent.futures
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import ConfirmationType, RiskLevel
from src.agent.exceptions import (
    BedrockClientError,
    MaxStepsExceededError,
    ToolExecutionError,
    ToolTimeoutError,
)
from src.agent.models import (
    AgentRunResult,
    ConfirmationRequest,
    ConversationState,
    PendingConfirmation,
    ToolCall,
    ToolDef,
)
from src.agent.utils.call_tracking import TrackingContext, set_tracking_context
from src.agent.utils.config import DEFAULT_AGENT_CONFIG, AgentConfig
from src.agent.utils.confirmation_classifier import (
    ClassificationParseError,
    classify_confirmation_response,
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
from src.agent.utils.tools.registry import ToolRegistry
from src.agent.utils.tools.selector import ToolSelector
from src.database.agent_tracking import (
    complete_agent_run,
    create_agent_conversation,
    create_agent_run,
    get_agent_conversation_by_id,
)

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import (
        MessageTypeDef,
        ToolConfigurationTypeDef,
    )
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

# Default system prompt for the agent (use {current_date} placeholder)
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools for managing tasks, goals, and reading lists.

Today's date is {current_date}.

When using tools:
1. Analyse the user's request carefully
2. Use the most appropriate tool for the task
3. If a query returns no results, inform the user rather than guessing
4. For updates or creates, confirm what was done after completion
5. Handle errors gracefully and explain any issues to the user
6. When users mention relative dates (e.g., "end of week", "next Friday"), calculate the actual date
7. Before calling create tools, check if the name/title is specific enough to find later. If vague (e.g., "Send email", "Meeting"), nudge the user for more details

Always be concise and helpful in your responses. Keep responses short and to the point."""


@dataclass
class _RunState:
    """Mutable state for an agent run."""

    messages: list[Any]  # MessageTypeDef
    tool_calls: list[ToolCall]
    steps_taken: int
    tools: dict[str, ToolDef]
    confirmed_tool_use_ids: set[str]
    all_tool_names: list[str]
    context_length: int = 0  # Number of messages from conversation context


@dataclass
class _ToolUseContext:
    """Context for processing a tool use request."""

    tool_use_id: str
    tool_name: str
    input_args: dict[str, Any]


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
        self.system_prompt = system_prompt
        self.require_confirmation = require_confirmation
        self._config = config

        # Executor for tool timeout handling (single worker for sequential execution)
        self._tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        logger.debug(
            f"Agent configured: selector={self._config.selector_model}, "
            f"chat={self._config.chat_model}, max_steps={self._config.max_steps}, "
            f"tool_timeout={self._config.tool_timeout_seconds}s"
        )

        # Create internal tool selector
        self._selector = ToolSelector(registry=registry, client=self.client)

        # Cache standard tool names (always included)
        self._standard_tool_names = [t.name for t in registry.get_standard_tools()]
        if self._standard_tool_names:
            logger.debug(f"Standard tools cached: {self._standard_tool_names}")

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

        Classifies the user's message as CONFIRM, DENY, or NEW_INTENT and
        processes accordingly.

        :param user_message: The user's response message.
        :param conv_state: Conversation state with pending confirmation.
        :returns: Result of handling the confirmation.
        """
        pending = conv_state.pending_confirmation
        if pending is None:
            # Should not happen, but handle gracefully
            return self._execute_run(user_message, None, conv_state)

        # Classify the user's response
        try:
            confirmation_type = classify_confirmation_response(
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
                response="I couldn't understand your response. Please try again with a clearer answer.",
                tool_calls=[],
                steps_taken=0,
                stop_reason="classification_error",
            )

        logger.info(f"Confirmation response classified as: {confirmation_type}")

        if confirmation_type == ConfirmationType.CONFIRM:
            # Clear pending and execute the tool directly
            clear_pending_confirmation(conv_state)

            logger.info(f"User confirmed action, executing tool: {pending.tool_name}")

            return self._execute_confirmed_tool(
                pending=pending,
                conv_state=conv_state,
                user_message=user_message,
            )

        if confirmation_type == ConfirmationType.DENY:
            # Clear pending and return cancellation
            clear_pending_confirmation(conv_state)

            # Add user message to context
            user_msg = cast(dict[str, Any], self.client.create_user_message(user_message))
            append_messages(conv_state, [user_msg])

            logger.info("User declined confirmation")

            return AgentRunResult(
                response="Action cancelled.",
                tool_calls=[],
                steps_taken=0,
                stop_reason="user_cancelled",
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

    def _execute_confirmed_tool(
        self,
        pending: PendingConfirmation,
        conv_state: ConversationState,
        user_message: str,
    ) -> AgentRunResult:
        """Execute a tool that was previously confirmed by the user.

        Directly executes the tool with saved arguments, then hands off to
        the agent loop to generate a response. The user's confirmation message
        is included so the LLM can see any additional requests (e.g., "yes,
        and also add X").

        :param pending: The confirmed pending action with tool details.
        :param conv_state: Conversation state for context.
        :param user_message: The user's confirmation message (may contain followup).
        :returns: Result of the agent run.
        """
        tool = self.registry.get(pending.tool_name)

        # Execute the tool and create the call record
        tool_result, tool_call = self._execute_and_create_tool_call(
            tool=tool,
            tool_use_id=pending.tool_use_id,
            input_args=pending.input_args,
        )

        logger.info(
            f"Confirmed tool executed: tool={pending.tool_name}, error={tool_call.is_error}"
        )

        # Build messages: context + user confirmation + assistant tool request + tool result
        # Include user message so LLM can see any additional requests in the confirmation
        context_messages = build_context_messages(conv_state)
        context_length = len(context_messages)
        user_confirmation_msg = self.client.create_user_message(user_message)
        assistant_tool_request = self.client.create_assistant_tool_use_message(
            tool_use_id=pending.tool_use_id,
            name=pending.tool_name,
            input_args=pending.input_args,
        )
        tool_result_msg = self.client.create_tool_result_message(
            pending.tool_use_id, tool_result, is_error=tool_call.is_error
        )

        messages: list[Any] = [
            *context_messages,
            user_confirmation_msg,
            assistant_tool_request,
            tool_result_msg,
        ]

        # Build tool config and state, then hand off to agent loop
        all_tool_names = pending.selected_tools or []

        state = _RunState(
            messages=messages,
            tool_calls=[tool_call],
            steps_taken=1,
            tools=self._build_tools_dict(all_tool_names),
            confirmed_tool_use_ids=set(),
            all_tool_names=all_tool_names,
            context_length=context_length,
        )

        return self._run_agent_loop(state, self._build_tool_config(all_tool_names), conv_state)

    def _resolve_tools(
        self,
        user_message: str,
        tool_names: list[str] | None,
        conv_state: ConversationState | None,
    ) -> list[str]:
        """Resolve the tools to use for this run.

        Uses context-aware tool selection:
        - First turn: Full selection based on user message
        - Subsequent turns: Additive mode - only adds tools if needed

        This prevents losing relevant tools when the user provides clarifying
        details (e.g., "both work and due 1st jan" after asking to create tasks).

        :param user_message: User message for auto-selection.
        :param tool_names: Explicit tool names override.
        :param conv_state: Conversation state with previous tool selection.
        :returns: List of selected tool names.
        """
        if tool_names is not None:
            return tool_names

        # Get current tools from conversation state (if any)
        current_tools = (
            conv_state.selected_tools
            if conv_state is not None and conv_state.selected_tools
            else None
        )

        # Select tools - additive mode if we have current tools
        selection = self._selector.select(
            user_message,
            model=self._config.selector_model,
            current_tools=current_tools,
        )

        if current_tools:
            # Additive mode: merge new tools with existing
            if selection.tool_names:
                merged = list(dict.fromkeys(current_tools + selection.tool_names))
                logger.info(f"Added tools {selection.tool_names}, now have: {merged}")
                return merged
            logger.debug(f"No new tools needed, keeping: {current_tools}")
            return current_tools
        # First turn: use full selection
        logger.info(
            f"Initial tool selection: {selection.tool_names}, reasoning={selection.reasoning}"
        )
        return selection.tool_names

    def _build_initial_messages(
        self,
        user_message: str,
        conv_state: ConversationState | None,
    ) -> tuple[list[Any], int]:
        """Build initial messages for the agent run.

        :param user_message: The user's input message.
        :param conv_state: Optional conversation state for context.
        :returns: Tuple of (messages, context_length) where context_length is
            the number of messages from conversation history.
        """
        if conv_state is not None:
            context_messages = build_context_messages(conv_state)
            new_user_message = self.client.create_user_message(user_message)
            return [*context_messages, new_user_message], len(context_messages)
        return [self.client.create_user_message(user_message)], 0

    def _build_tool_config(
        self,
        tool_names: list[str],
    ) -> ToolConfigurationTypeDef | None:
        """Build Bedrock tool configuration from tool names.

        :param tool_names: List of tool names to include.
        :returns: Tool configuration or None if no tools.
        """
        if not tool_names:
            logger.info("No tools available for this request")
            return None
        return cast(
            "ToolConfigurationTypeDef",
            self.registry.to_bedrock_tool_config(tool_names),
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
            tool_result = {"error": e.error}
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
        conv_state: ConversationState | None = None,
    ) -> AgentRunResult:
        """Execute the agent run logic.

        :param user_message: The user's input message.
        :param tool_names: Optional list of tool names. If None, auto-selects.
        :param conv_state: Optional conversation state for context.
        :returns: Result of the agent run.
        """
        selected_tools = self._resolve_tools(user_message, tool_names, conv_state)

        # Merge standard tools with selected tools (deduplicated)
        all_tool_names = list(dict.fromkeys(self._standard_tool_names + selected_tools))

        # Update conversation state with selected tools
        if conv_state is not None:
            conv_state.selected_tools = selected_tools

        tool_config = self._build_tool_config(all_tool_names)
        initial_messages, context_length = self._build_initial_messages(user_message, conv_state)

        state = _RunState(
            messages=initial_messages,
            tool_calls=[],
            steps_taken=0,
            tools=self._build_tools_dict(all_tool_names),
            confirmed_tool_use_ids=set(),
            all_tool_names=all_tool_names,
            context_length=context_length,
        )

        logger.info(
            f"Starting agent run: tools={all_tool_names or '(none)'}, "
            f"max_steps={self._config.max_steps}"
        )

        return self._run_agent_loop(state, tool_config, conv_state)

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
        messages: list[MessageTypeDef],
        tool_config: ToolConfigurationTypeDef | None,
    ) -> dict[str, Any]:
        """Call the LLM and return the response."""
        # Format system prompt with current date
        formatted_prompt = self.system_prompt.format(current_date=date.today().isoformat())

        try:
            return self.client.converse(
                messages=messages,
                model_id=self._config.chat_model,
                system_prompt=formatted_prompt,
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
        provide a tool_result for each one. This method handles all tool
        uses in the response.

        :returns: AgentRunResult if the run should stop, None to continue.
        """
        tool_uses = self.client.parse_tool_use(response)
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
                tool_use_id=tool_use["toolUseId"],
                tool_name=tool_use["name"],
                input_args=tool_use["input"],
            )
            contexts.append(ctx)
            logger.info(f"Tool use requested: tool={ctx.tool_name}, id={ctx.tool_use_id}")

        # Check if ANY tool is unknown - if so, error all
        unknown_tools = [ctx for ctx in contexts if ctx.tool_name not in state.tools]
        if unknown_tools:
            self._handle_unknown_tool(tool_uses, state, response)
            return None

        # Check if ANY tool requires confirmation - if so, pause on first sensitive one
        for ctx in contexts:
            tool = state.tools[ctx.tool_name]
            confirmation_result = self._check_confirmation_required(ctx, tool, state, conv_state)
            if confirmation_result is not None:
                return confirmation_result

        # Execute ALL tools and collect results
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
                {
                    "toolResult": {
                        "toolUseId": ctx.tool_use_id,
                        "content": [{"json": tool_result}],
                        "status": "error" if tool_call.is_error else "success",
                    }
                }
            )

        # Add single message with ALL tool results
        state.messages.append({"role": "user", "content": tool_result_contents})

    def _handle_unknown_tool(
        self,
        tool_uses: list[dict[str, Any]],
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
            tool_use_id = tool_use["toolUseId"]
            tool_name = tool_use["name"]
            input_args = tool_use["input"]

            if tool_name not in state.tools:
                logger.error(f"LLM requested unknown tool: {tool_name}")
                error_result = {"error": f"Unknown tool: {tool_name}"}
            else:
                # Tool exists but we can't execute it because another tool
                # in this batch is unknown - we need to bail out entirely
                logger.warning(f"Skipping tool {tool_name} due to unknown tool in same request")
                error_result = {"error": "Execution skipped due to unknown tool in batch"}

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
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": error_result}],
                        "status": "error",
                    }
                }
            )

        # Add single message with ALL tool results
        state.messages.append({"role": "user", "content": tool_result_contents})

    def _check_confirmation_required(
        self,
        ctx: _ToolUseContext,
        tool: ToolDef,
        state: _RunState,
        conv_state: ConversationState | None,
    ) -> AgentRunResult | None:
        """Check if a sensitive tool requires confirmation.

        :returns: AgentRunResult if confirmation is required, None otherwise.
        """
        if not self.require_confirmation:
            return None
        if tool.risk_level != RiskLevel.SENSITIVE:
            return None
        if ctx.tool_use_id in state.confirmed_tool_use_ids:
            return None

        logger.info(f"Sensitive tool requires confirmation: tool={ctx.tool_name}")
        action_summary = self._generate_action_summary(tool.description, ctx.input_args)

        # Store pending confirmation in conversation state if available
        if conv_state is not None:
            pending = PendingConfirmation(
                tool_use_id=ctx.tool_use_id,
                tool_name=ctx.tool_name,
                tool_description=tool.description,
                input_args=ctx.input_args,
                action_summary=action_summary,
                selected_tools=state.all_tool_names,
            )
            set_pending_confirmation(conv_state, pending)

            # Save current messages to state for resumption
            # Only append new messages (skip context that's already stored)
            new_messages = state.messages[state.context_length :]
            append_messages(conv_state, new_messages)

        return AgentRunResult(
            response="",
            tool_calls=state.tool_calls,
            steps_taken=state.steps_taken,
            stop_reason="confirmation_required",
            confirmation_request=ConfirmationRequest(
                tool_name=ctx.tool_name,
                tool_description=tool.description,
                input_args=ctx.input_args,
                action_summary=action_summary,
                tool_use_id=ctx.tool_use_id,
            ),
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
