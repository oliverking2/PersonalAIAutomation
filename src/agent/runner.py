"""Agent runner for executing tool-based LLM workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from src.agent.client import BedrockClient
from src.agent.enums import RiskLevel
from src.agent.exceptions import (
    BedrockClientError,
    MaxStepsExceededError,
    ToolExecutionError,
)
from src.agent.models import AgentRunResult, ConfirmationRequest, ToolCall, ToolDef
from src.agent.registry import ToolRegistry

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import (
        MessageTypeDef,
        ToolConfigurationTypeDef,
    )

logger = logging.getLogger(__name__)

# Default maximum number of tool execution steps
DEFAULT_MAX_STEPS = 5

# Default system prompt for the agent
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools for managing tasks, goals, and reading lists.

When using tools:
1. Analyse the user's request carefully
2. Use the most appropriate tool for the task
3. If a query returns no results, inform the user rather than guessing
4. For updates or creates, confirm what was done after completion
5. Handle errors gracefully and explain any issues to the user

Always be concise and helpful in your responses."""


@dataclass
class _RunState:
    """Mutable state for an agent run."""

    messages: list[Any]  # MessageTypeDef
    tool_calls: list[ToolCall]
    steps_taken: int
    tools: dict[str, ToolDef]
    confirmed_tool_use_ids: set[str]


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
    """

    def __init__(
        self,
        registry: ToolRegistry,
        client: BedrockClient | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: int = DEFAULT_MAX_STEPS,
        require_confirmation: bool = True,
    ) -> None:
        """Initialise the agent runner.

        :param registry: Tool registry containing available tools.
        :param client: Bedrock client for LLM calls. Creates one if not provided.
        :param system_prompt: System prompt for the agent.
        :param max_steps: Maximum number of tool execution steps.
        :param require_confirmation: Whether to require confirmation for sensitive tools.
        """
        self.registry = registry
        self.client = client or BedrockClient()
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.require_confirmation = require_confirmation

    def run(
        self,
        user_message: str,
        tool_names: list[str],
        confirmed_tool_use_ids: set[str] | None = None,
    ) -> AgentRunResult:
        """Execute the agent with the given user message and tools.

        :param user_message: The user's input message.
        :param tool_names: Names of tools to make available to the agent.
        :param confirmed_tool_use_ids: Set of tool use IDs that have been confirmed.
        :returns: Result of the agent run.
        :raises MaxStepsExceededError: If the agent exceeds max_steps.
        :raises BedrockClientError: If the Bedrock API call fails.
        :raises ToolNotFoundError: If a requested tool is not found.
        """
        tool_config = cast(
            "ToolConfigurationTypeDef",
            self.registry.to_bedrock_tool_config(tool_names),
        )
        state = _RunState(
            messages=[self.client.create_user_message(user_message)],
            tool_calls=[],
            steps_taken=0,
            tools={t.name: t for t in self.registry.get_many(tool_names)},
            confirmed_tool_use_ids=confirmed_tool_use_ids or set(),
        )

        logger.info(f"Starting agent run: tools={tool_names}, max_steps={self.max_steps}")

        while True:
            if state.steps_taken >= self.max_steps:
                logger.warning(f"Agent exceeded max steps: max={self.max_steps}")
                raise MaxStepsExceededError(self.max_steps, state.steps_taken)

            response = self._call_llm(state.messages, tool_config)
            stop_reason = self.client.get_stop_reason(response)
            logger.debug(f"Agent step {state.steps_taken}: stop_reason={stop_reason}")

            if stop_reason == "tool_use":
                result = self._handle_tool_use(response, state)
                if result is not None:
                    return result
                state.steps_taken += 1
            elif stop_reason == "end_turn":
                return self._build_final_result(response, state, "end_turn")
            else:
                logger.warning(f"Unexpected stop reason: {stop_reason}")
                return self._build_final_result(response, state, stop_reason)

    def _call_llm(
        self,
        messages: list[MessageTypeDef],
        tool_config: ToolConfigurationTypeDef,
    ) -> dict[str, Any]:
        """Call the LLM and return the response."""
        try:
            return self.client.converse(
                messages=messages,
                system_prompt=self.system_prompt,
                tool_config=tool_config,
            )
        except BedrockClientError:
            logger.exception("Bedrock API call failed during agent run")
            raise

    def _handle_tool_use(
        self,
        response: dict[str, Any],
        state: _RunState,
    ) -> AgentRunResult | None:
        """Handle a tool use response from the LLM.

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

        tool_use = tool_uses[0]
        ctx = _ToolUseContext(
            tool_use_id=tool_use["toolUseId"],
            tool_name=tool_use["name"],
            input_args=tool_use["input"],
        )

        logger.info(f"Tool use requested: tool={ctx.tool_name}, id={ctx.tool_use_id}")

        if ctx.tool_name not in state.tools:
            self._handle_unknown_tool(ctx, state, response)
            return None

        tool = state.tools[ctx.tool_name]

        confirmation_result = self._check_confirmation_required(ctx, tool, state)
        if confirmation_result is not None:
            return confirmation_result

        self._execute_and_record_tool(ctx, tool, state, response)
        return None

    def _handle_unknown_tool(
        self,
        ctx: _ToolUseContext,
        state: _RunState,
        response: dict[str, Any],
    ) -> None:
        """Handle a request for an unknown tool."""
        logger.error(f"LLM requested unknown tool: {ctx.tool_name}")
        error_result = {"error": f"Unknown tool: {ctx.tool_name}"}
        state.tool_calls.append(
            ToolCall(
                tool_use_id=ctx.tool_use_id,
                tool_name=ctx.tool_name,
                input_args=ctx.input_args,
                output=error_result,
                is_error=True,
            )
        )
        state.messages.append(response["output"]["message"])
        state.messages.append(
            self.client.create_tool_result_message(ctx.tool_use_id, error_result, is_error=True)
        )

    def _check_confirmation_required(
        self,
        ctx: _ToolUseContext,
        tool: ToolDef,
        state: _RunState,
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

    def _execute_and_record_tool(
        self,
        ctx: _ToolUseContext,
        tool: ToolDef,
        state: _RunState,
        response: dict[str, Any],
    ) -> None:
        """Execute a tool and record the result."""
        try:
            tool_result = self._execute_tool(tool, ctx.input_args)
            is_error = False
        except ToolExecutionError as e:
            logger.warning(f"Tool execution failed: {e}")
            tool_result = {"error": e.error}
            is_error = True

        state.tool_calls.append(
            ToolCall(
                tool_use_id=ctx.tool_use_id,
                tool_name=ctx.tool_name,
                input_args=ctx.input_args,
                output=tool_result,
                is_error=is_error,
            )
        )
        state.messages.append(response["output"]["message"])
        state.messages.append(
            self.client.create_tool_result_message(ctx.tool_use_id, tool_result, is_error=is_error)
        )

    def _build_final_result(
        self,
        response: dict[str, Any],
        state: _RunState,
        stop_reason: str,
    ) -> AgentRunResult:
        """Build the final result when the agent is done."""
        final_response = self.client.parse_text_response(response)
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

    def run_with_confirmation(
        self,
        user_message: str,
        tool_names: list[str],
        pending_result: AgentRunResult,
        confirmed: bool,
    ) -> AgentRunResult:
        """Continue a run after user confirmation for a sensitive tool.

        :param user_message: Original user message.
        :param tool_names: Names of tools available to the agent.
        :param pending_result: Previous result that required confirmation.
        :param confirmed: Whether the user confirmed the action.
        :returns: Updated result after processing confirmation.
        :raises ValueError: If pending_result does not require confirmation.
        """
        if (
            pending_result.stop_reason != "confirmation_required"
            or pending_result.confirmation_request is None
        ):
            raise ValueError("pending_result does not require confirmation")

        if not confirmed:
            logger.info("User declined confirmation, returning denial response")
            return AgentRunResult(
                response="Action cancelled by user.",
                tool_calls=pending_result.tool_calls,
                steps_taken=pending_result.steps_taken,
                stop_reason="user_cancelled",
            )

        confirmed_ids = {pending_result.confirmation_request.tool_use_id}
        logger.info(f"User confirmed action, continuing run: confirmed_ids={confirmed_ids}")

        return self.run(
            user_message=user_message,
            tool_names=tool_names,
            confirmed_tool_use_ids=confirmed_ids,
        )

    def _execute_tool(self, tool: ToolDef, input_args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with the given arguments.

        :param tool: Tool definition to execute.
        :param input_args: Arguments for the tool.
        :returns: Tool execution result.
        :raises ToolExecutionError: If execution fails.
        """
        try:
            validated_args = tool.args_model(**input_args)
            result = tool.handler(validated_args)
            logger.debug(f"Tool executed successfully: tool={tool.name}")
            return result
        except ValidationError as e:
            logger.warning(f"Tool argument validation failed: tool={tool.name}, error={e}")
            raise ToolExecutionError(tool.name, f"Invalid arguments: {e}") from e
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
