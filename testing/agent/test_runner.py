"""Tests for AgentRunner."""

import time
import unittest
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.agent.bedrock_client import ToolUseBlock
from src.agent.enums import ConfidenceLevel, RiskLevel
from src.agent.exceptions import MaxStepsExceededError, ToolExecutionError, ToolTimeoutError
from src.agent.models import ToolDef
from src.agent.runner import DEFAULT_SYSTEM_PROMPT, AgentRunner
from src.agent.utils.confidence_classifier import ConfidenceClassification
from src.agent.utils.config import DEFAULT_AGENT_CONFIG, AgentConfig
from src.agent.utils.tools.registry import ToolRegistry


class DummyArgs(BaseModel):
    """Dummy argument model for testing."""

    value: str


def dummy_handler(args: DummyArgs) -> dict[str, Any]:
    """Return dummy data for testing."""
    return {"result": args.value}


def error_handler(args: DummyArgs) -> dict[str, Any]:
    """Raise an error for testing."""
    raise RuntimeError("Handler error")


def _create_mock_db_objects() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create mock database objects for testing.

    :returns: Tuple of (mock_session, mock_conversation, mock_run).
    """
    mock_session = MagicMock()
    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.messages_json = None
    mock_conversation.selected_tools = None
    mock_conversation.pending_confirmation = None
    mock_conversation.summary = None
    mock_conversation.message_count = 0
    mock_conversation.last_summarised_at = None

    mock_run = MagicMock()
    mock_run.id = uuid.uuid4()

    return mock_session, mock_conversation, mock_run


class TestAgentRunner(unittest.TestCase):
    """Tests for AgentRunner."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()

        # Create mock database objects
        self.mock_session, self.mock_conversation, self.mock_run = _create_mock_db_objects()

        # Register a safe tool
        self.safe_tool = ToolDef(
            name="safe_tool",
            description="A safe test tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.safe_tool)

        # Register a sensitive tool
        self.sensitive_tool = ToolDef(
            name="sensitive_tool",
            description="A sensitive test tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.sensitive_tool)

        # Register an error tool
        self.error_tool = ToolDef(
            name="error_tool",
            description="A tool that errors",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=error_handler,
        )
        self.registry.register(self.error_tool)

        self.mock_client = MagicMock()

    def test_init_with_defaults(self) -> None:
        """Test initialisation with default values."""
        with patch.dict("os.environ", {"BEDROCK_MODEL_ID": "test-model"}):
            runner = AgentRunner(registry=self.registry)

            self.assertEqual(runner.system_prompt, DEFAULT_SYSTEM_PROMPT)
            self.assertEqual(runner._config.max_steps, DEFAULT_AGENT_CONFIG.max_steps)
            self.assertTrue(runner.require_confirmation)

    def test_init_with_custom_values(self) -> None:
        """Test initialisation with custom values."""
        custom_config = AgentConfig(max_steps=10, max_tokens=8192)
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            system_prompt="Custom prompt",
            require_confirmation=False,
            config=custom_config,
        )

        self.assertEqual(runner.system_prompt, "Custom prompt")
        self.assertEqual(runner._config.max_steps, 10)
        self.assertEqual(runner._config.max_tokens, 8192)
        self.assertFalse(runner.require_confirmation)

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_simple_query_no_tools(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test run when model responds without using tools."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Hello"}],
        }
        self.mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Hi there!"}]}},
            "stopReason": "end_turn",
        }
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Hi there!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run("Hello", self.mock_session, tool_names=["safe_tool"])

        self.assertEqual(result.response, "Hi there!")
        self.assertEqual(result.tool_calls, [])
        self.assertEqual(result.steps_taken, 0)
        self.assertEqual(result.stop_reason, "end_turn")

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_with_safe_tool(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test run where model uses a safe tool."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Query something"}],
        }

        # First response: model wants to use tool
        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-123",
                                "name": "safe_tool",
                                "input": {"value": "test"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        # Second response: model gives final answer
        final_response = {
            "output": {"message": {"content": [{"text": "Done!"}]}},
            "stopReason": "end_turn",
        }

        self.mock_client.converse.side_effect = [tool_response, final_response]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-123", name="safe_tool", input={"value": "test"})
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "tool-123"}}],
        }
        self.mock_client.parse_text_response.return_value = "Done!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run("Query something", self.mock_session, tool_names=["safe_tool"])

        self.assertEqual(result.response, "Done!")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, "safe_tool")
        self.assertEqual(result.tool_calls[0].input_args, {"value": "test"})
        self.assertEqual(result.tool_calls[0].output, {"result": "test"})
        self.assertFalse(result.tool_calls[0].is_error)
        self.assertEqual(result.steps_taken, 1)
        self.assertEqual(result.stop_reason, "end_turn")

    @patch("src.agent.runner.classify_action_confidence")
    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_sensitive_tool_requires_confirmation(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """Test that sensitive tools require confirmation when NEEDS_CONFIRMATION."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        # Mock confidence classifier to return NEEDS_CONFIRMATION
        mock_classify.return_value = ConfidenceClassification(
            level=ConfidenceLevel.NEEDS_CONFIRMATION,
            reasoning="Vague request requires confirmation",
        )

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Update something"}],
        }

        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-456",
                                "name": "sensitive_tool",
                                "input": {"value": "update"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        self.mock_client.converse.return_value = tool_response
        self.mock_client.get_stop_reason.return_value = "tool_use"
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-456", name="sensitive_tool", input={"value": "update"})
        ]

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            require_confirmation=True,
        )

        result = runner.run("Update something", self.mock_session, tool_names=["sensitive_tool"])

        self.assertEqual(result.stop_reason, "confirmation_required")
        self.assertIsNotNone(result.confirmation_request)
        self.assertEqual(len(result.confirmation_request.tools), 1)
        tool_action = result.confirmation_request.tools[0]
        self.assertEqual(tool_action.tool_name, "sensitive_tool")
        self.assertEqual(tool_action.input_args, {"value": "update"})
        self.assertEqual(tool_action.tool_use_id, "tool-456")
        self.assertEqual(result.steps_taken, 0)

    @patch("src.agent.runner.classify_action_confidence")
    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_sensitive_tool_executes_immediately_when_explicit(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """Test that sensitive tools execute immediately when EXPLICIT confidence."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        # Mock confidence classifier to return EXPLICIT
        mock_classify.return_value = ConfidenceClassification(
            level=ConfidenceLevel.EXPLICIT,
            reasoning="User explicitly requested this update",
        )

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Update the task description to 'New description'"}],
        }

        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-456",
                                "name": "sensitive_tool",
                                "input": {"value": "update"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        final_response = {
            "output": {"message": {"content": [{"text": "Updated!"}]}},
            "stopReason": "end_turn",
        }

        self.mock_client.converse.side_effect = [tool_response, final_response]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-456", name="sensitive_tool", input={"value": "update"})
        ]
        self.mock_client.parse_text_response.return_value = "Updated!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            require_confirmation=True,
        )

        result = runner.run(
            "Update the task description to 'New description'",
            self.mock_session,
            tool_names=["sensitive_tool"],
        )

        # Should execute immediately without confirmation
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertIsNone(result.confirmation_request)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, "sensitive_tool")
        self.assertFalse(result.tool_calls[0].is_error)

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_sensitive_tool_with_confirmation_disabled(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test that sensitive tools run without confirmation when disabled."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Update something"}],
        }

        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-456",
                                "name": "sensitive_tool",
                                "input": {"value": "update"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        final_response = {
            "output": {"message": {"content": [{"text": "Updated!"}]}},
            "stopReason": "end_turn",
        }

        self.mock_client.converse.side_effect = [tool_response, final_response]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-456", name="sensitive_tool", input={"value": "update"})
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "tool-456"}}],
        }
        self.mock_client.parse_text_response.return_value = "Updated!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            require_confirmation=False,
        )

        result = runner.run("Update something", self.mock_session, tool_names=["sensitive_tool"])

        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, "sensitive_tool")

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_max_steps_exceeded(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test that max steps limit is enforced."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Query"}],
        }

        # Model keeps wanting to use tools
        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-x",
                                "name": "safe_tool",
                                "input": {"value": "test"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        self.mock_client.converse.return_value = tool_response
        self.mock_client.get_stop_reason.return_value = "tool_use"
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-x", name="safe_tool", input={"value": "test"})
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "tool-x"}}],
        }

        config = AgentConfig(max_steps=3)
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            config=config,
        )

        with self.assertRaises(MaxStepsExceededError) as ctx:
            runner.run("Query", self.mock_session, tool_names=["safe_tool"])

        self.assertEqual(ctx.exception.max_steps, 3)
        self.assertEqual(ctx.exception.steps_taken, 3)

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_handles_tool_execution_error(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test that tool execution errors are handled gracefully."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Query"}],
        }

        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-err",
                                "name": "error_tool",
                                "input": {"value": "test"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        final_response = {
            "output": {"message": {"content": [{"text": "Error handled"}]}},
            "stopReason": "end_turn",
        }

        self.mock_client.converse.side_effect = [tool_response, final_response]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-err", name="error_tool", input={"value": "test"})
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "tool-err", "status": "error"}}],
        }
        self.mock_client.parse_text_response.return_value = "Error handled"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run("Query", self.mock_session, tool_names=["error_tool"])

        self.assertEqual(len(result.tool_calls), 1)
        self.assertTrue(result.tool_calls[0].is_error)
        self.assertIn("error", result.tool_calls[0].output)

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_handles_unknown_tool(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test that unknown tool requests are handled gracefully."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Query"}],
        }

        # Model requests a tool that doesn't exist
        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-unknown",
                                "name": "nonexistent_tool",
                                "input": {"value": "test"},
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        final_response = {
            "output": {"message": {"content": [{"text": "Unknown tool handled"}]}},
            "stopReason": "end_turn",
        }

        self.mock_client.converse.side_effect = [tool_response, final_response]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-unknown", name="nonexistent_tool", input={"value": "test"})
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "tool-unknown", "status": "error"}}],
        }
        self.mock_client.parse_text_response.return_value = "Unknown tool handled"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run("Query", self.mock_session, tool_names=["safe_tool"])

        self.assertEqual(len(result.tool_calls), 1)
        self.assertTrue(result.tool_calls[0].is_error)
        self.assertIn("Unknown tool", result.tool_calls[0].output["error"])

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_handles_max_tokens_stop_reason(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test that max_tokens stop reason returns user-friendly error."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Add 20 reading items"}],
        }

        # Model response is truncated due to max_tokens
        truncated_response = {
            "output": {
                "message": {"content": [{"text": "I'll add all these reading items for you..."}]}
            },
            "stopReason": "max_tokens",
        }

        self.mock_client.converse.return_value = truncated_response
        self.mock_client.get_stop_reason.return_value = "max_tokens"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run("Add 20 reading items", self.mock_session, tool_names=["safe_tool"])

        self.assertEqual(result.stop_reason, "max_tokens")
        self.assertIn("breaking it into smaller parts", result.response)
        self.assertEqual(result.tool_calls, [])
        self.assertEqual(result.steps_taken, 0)

    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_passes_max_tokens_to_converse(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
    ) -> None:
        """Test that max_tokens config is passed to converse call."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Hello"}],
        }
        self.mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Hi there!"}]}},
            "stopReason": "end_turn",
        }
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Hi there!"

        custom_config = AgentConfig(max_tokens=8192)
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            config=custom_config,
        )

        runner.run("Hello", self.mock_session, tool_names=["safe_tool"])

        # Verify converse was called with max_tokens from config
        self.mock_client.converse.assert_called()
        call_kwargs = self.mock_client.converse.call_args.kwargs
        self.assertEqual(call_kwargs["max_tokens"], 8192)

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_run_multiple_tools_in_single_response(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that multiple tool uses in a single response are all executed."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "Create two tasks"}],
        }

        # Response contains TWO tool uses
        tool_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-1",
                                "name": "safe_tool",
                                "input": {"value": "first"},
                            }
                        },
                        {
                            "toolUse": {
                                "toolUseId": "tool-2",
                                "name": "safe_tool",
                                "input": {"value": "second"},
                            }
                        },
                    ]
                }
            },
            "stopReason": "tool_use",
        }

        final_response = {
            "output": {"message": {"content": [{"text": "Created both!"}]}},
            "stopReason": "end_turn",
        }

        self.mock_client.converse.side_effect = [tool_response, final_response]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="tool-1", name="safe_tool", input={"value": "first"}),
            ToolUseBlock(id="tool-2", name="safe_tool", input={"value": "second"}),
        ]
        self.mock_client.create_tool_result_message.side_effect = [
            {"role": "user", "content": [{"toolResult": {"toolUseId": "tool-1"}}]},
            {"role": "user", "content": [{"toolResult": {"toolUseId": "tool-2"}}]},
        ]
        self.mock_client.parse_text_response.return_value = "Created both!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run("Create two tasks", self.mock_session, tool_names=["safe_tool"])

        self.assertEqual(result.response, "Created both!")
        self.assertEqual(len(result.tool_calls), 2)
        self.assertEqual(result.tool_calls[0].tool_name, "safe_tool")
        self.assertEqual(result.tool_calls[0].input_args, {"value": "first"})
        self.assertEqual(result.tool_calls[0].output, {"result": "first"})
        self.assertFalse(result.tool_calls[0].is_error)
        self.assertEqual(result.tool_calls[1].tool_name, "safe_tool")
        self.assertEqual(result.tool_calls[1].input_args, {"value": "second"})
        self.assertEqual(result.tool_calls[1].output, {"result": "second"})
        self.assertFalse(result.tool_calls[1].is_error)
        self.assertEqual(result.steps_taken, 1)
        self.assertEqual(result.stop_reason, "end_turn")


class TestAgentRunnerExecuteTool(unittest.TestCase):
    """Tests for AgentRunner._execute_tool method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()
        self.mock_client = MagicMock()

    def test_execute_tool_success(self) -> None:
        """Test successful tool execution."""
        tool = ToolDef(
            name="test_tool",
            description="Test tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner._execute_tool(tool, {"value": "hello"})

        self.assertEqual(result, {"result": "hello"})

    def test_execute_tool_validation_error(self) -> None:
        """Test tool execution with invalid arguments."""
        tool = ToolDef(
            name="test_tool",
            description="Test tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        with self.assertRaises(ToolExecutionError) as ctx:
            runner._execute_tool(tool, {"wrong_arg": "hello"})

        self.assertEqual(ctx.exception.tool_name, "test_tool")
        self.assertIn("Invalid arguments", ctx.exception.error)

    def test_execute_tool_handler_error(self) -> None:
        """Test tool execution when handler raises error."""
        tool = ToolDef(
            name="error_tool",
            description="Error tool",
            args_model=DummyArgs,
            handler=error_handler,
        )

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        with self.assertRaises(ToolExecutionError) as ctx:
            runner._execute_tool(tool, {"value": "hello"})

        self.assertEqual(ctx.exception.tool_name, "error_tool")
        self.assertIn("Handler error", ctx.exception.error)


class TestAgentRunnerGenerateActionSummary(unittest.TestCase):
    """Tests for AgentRunner._generate_action_summary method."""

    def test_generate_action_summary(self) -> None:
        """Test action summary generation."""
        summary = AgentRunner._generate_action_summary(
            tool_description="Create a new task in the task tracker",
            input_args={"name": "My Task", "priority": "High"},
        )

        self.assertIn("Create a new task", summary)
        self.assertIn("name='My Task'", summary)
        self.assertIn("priority='High'", summary)


class TestMessageDuplicationPrevention(unittest.TestCase):
    """Tests to ensure messages are not duplicated across conversation turns.

    These tests verify that the fix for the message duplication bug is working:
    - Only NEW messages from each run are appended to conversation state
    - Context messages (already in state) are not re-appended
    - Multi-turn conversations maintain correct message count
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()

        # Create mock database objects
        self.mock_session, self.mock_conversation, self.mock_run = _create_mock_db_objects()

        # Register a safe tool
        self.safe_tool = ToolDef(
            name="safe_tool",
            description="A safe test tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.safe_tool)

        # Register a sensitive tool
        self.sensitive_tool = ToolDef(
            name="sensitive_tool",
            description="A sensitive test tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.sensitive_tool)

        self.mock_client = MagicMock()

    def _make_user_message(self, text: str) -> dict[str, Any]:
        """Create a user message dict."""
        return {"role": "user", "content": [{"text": text}]}

    def _make_assistant_message(self, text: str) -> dict[str, Any]:
        """Create an assistant message dict."""
        return {"role": "assistant", "content": [{"text": text}]}

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_first_turn_stores_only_new_messages(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that first turn stores exactly the new user and assistant messages."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        user_msg = self._make_user_message("Hello")
        assistant_msg = self._make_assistant_message("Hi there!")

        self.mock_client.create_user_message.return_value = user_msg
        self.mock_client.converse.return_value = {
            "output": {"message": assistant_msg},
            "stopReason": "end_turn",
        }
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Hi there!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        runner.run("Hello", self.mock_session, tool_names=["safe_tool"])

        # Check saved state has exactly 2 messages (user + assistant)
        mock_save_state.assert_called_once()
        saved_state = mock_save_state.call_args[0][2]  # Third argument is conv_state
        self.assertEqual(len(saved_state.messages), 2)
        self.assertEqual(saved_state.messages[0]["role"], "user")
        self.assertEqual(saved_state.messages[1]["role"], "assistant")

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.get_agent_conversation_by_id")
    def test_second_turn_does_not_duplicate_first_turn_messages(
        self,
        mock_get_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that second turn doesn't duplicate messages from the first turn."""
        # Simulate first turn's messages already in conversation state
        existing_messages = [
            self._make_user_message("First message"),
            self._make_assistant_message("First response"),
        ]
        self.mock_conversation.messages_json = existing_messages
        self.mock_conversation.message_count = 2
        mock_get_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        # Second turn messages
        user_msg = self._make_user_message("Second message")
        assistant_msg = self._make_assistant_message("Second response")

        self.mock_client.create_user_message.return_value = user_msg
        self.mock_client.converse.return_value = {
            "output": {"message": assistant_msg},
            "stopReason": "end_turn",
        }
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Second response"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        runner.run(
            "Second message",
            self.mock_session,
            conversation_id=self.mock_conversation.id,
            tool_names=["safe_tool"],
        )

        # Check saved state has exactly 4 messages (2 existing + 2 new)
        mock_save_state.assert_called_once()
        saved_state = mock_save_state.call_args[0][2]

        # Should have 4 total messages, not 6 (which would indicate duplication)
        self.assertEqual(len(saved_state.messages), 4)

        # Verify message order: first turn's messages + second turn's messages
        self.assertEqual(saved_state.messages[0]["content"][0]["text"], "First message")
        self.assertEqual(saved_state.messages[1]["content"][0]["text"], "First response")
        self.assertEqual(saved_state.messages[2]["role"], "user")
        self.assertEqual(saved_state.messages[3]["role"], "assistant")

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.get_agent_conversation_by_id")
    def test_third_turn_no_exponential_growth(
        self,
        mock_get_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that third turn doesn't cause exponential message growth.

        Before the fix, messages would grow exponentially:
        - Turn 1: 2 messages
        - Turn 2: 6 messages (2 context + 4 = 2 + 2 + 2)
        - Turn 3: 14 messages (6 context + 8 = 6 + 6 + 2)

        After the fix, messages should grow linearly:
        - Turn 1: 2 messages
        - Turn 2: 4 messages
        - Turn 3: 6 messages
        """
        # Simulate two turns already completed
        existing_messages = [
            self._make_user_message("First message"),
            self._make_assistant_message("First response"),
            self._make_user_message("Second message"),
            self._make_assistant_message("Second response"),
        ]
        self.mock_conversation.messages_json = existing_messages
        self.mock_conversation.message_count = 4
        mock_get_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        # Third turn messages
        user_msg = self._make_user_message("Third message")
        assistant_msg = self._make_assistant_message("Third response")

        self.mock_client.create_user_message.return_value = user_msg
        self.mock_client.converse.return_value = {
            "output": {"message": assistant_msg},
            "stopReason": "end_turn",
        }
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Third response"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        runner.run(
            "Third message",
            self.mock_session,
            conversation_id=self.mock_conversation.id,
            tool_names=["safe_tool"],
        )

        # Check saved state has exactly 6 messages (4 existing + 2 new)
        # NOT 14 messages (which would indicate exponential growth)
        mock_save_state.assert_called_once()
        saved_state = mock_save_state.call_args[0][2]
        self.assertEqual(len(saved_state.messages), 6)

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.get_agent_conversation_by_id")
    def test_tool_use_turn_no_duplication(
        self,
        mock_get_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that tool-use turns don't duplicate messages."""
        existing_messages = [
            self._make_user_message("Previous message"),
            self._make_assistant_message("Previous response"),
        ]
        self.mock_conversation.messages_json = existing_messages
        self.mock_conversation.message_count = 2
        mock_get_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        user_msg = self._make_user_message("Use the tool")
        tool_use_msg = {
            "role": "assistant",
            "content": [{"toolUse": {"toolUseId": "t1", "name": "safe_tool", "input": {}}}],
        }
        final_msg = self._make_assistant_message("Done with tool")

        self.mock_client.create_user_message.return_value = user_msg
        self.mock_client.converse.side_effect = [
            {"output": {"message": tool_use_msg}, "stopReason": "tool_use"},
            {"output": {"message": final_msg}, "stopReason": "end_turn"},
        ]
        self.mock_client.get_stop_reason.side_effect = ["tool_use", "end_turn"]
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="t1", name="safe_tool", input={"value": "test"})
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "t1"}}],
        }
        self.mock_client.parse_text_response.return_value = "Done with tool"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        runner.run(
            "Use the tool",
            self.mock_session,
            conversation_id=self.mock_conversation.id,
            tool_names=["safe_tool"],
        )

        mock_save_state.assert_called_once()
        saved_state = mock_save_state.call_args[0][2]

        # Should have: 2 existing + 1 user + 1 tool_use + 1 tool_result + 1 final = 6
        # NOT 8 (which would include duplicated context)
        self.assertEqual(len(saved_state.messages), 6)

    @patch("src.agent.runner.classify_action_confidence")
    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.get_agent_conversation_by_id")
    def test_confirmation_pending_no_duplication(
        self,
        mock_get_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
        mock_classify: MagicMock,
    ) -> None:
        """Test that requesting confirmation doesn't duplicate messages."""
        mock_classify.return_value = ConfidenceClassification(
            level=ConfidenceLevel.NEEDS_CONFIRMATION,
            reasoning="Needs confirmation for this test",
        )
        existing_messages = [
            self._make_user_message("Previous message"),
            self._make_assistant_message("Previous response"),
        ]
        self.mock_conversation.messages_json = existing_messages
        self.mock_conversation.message_count = 2
        mock_get_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        user_msg = self._make_user_message("Update something")
        tool_use_msg = {
            "role": "assistant",
            "content": [
                {"toolUse": {"toolUseId": "t1", "name": "sensitive_tool", "input": {"value": "x"}}}
            ],
        }

        self.mock_client.create_user_message.return_value = user_msg
        self.mock_client.converse.return_value = {
            "output": {"message": tool_use_msg},
            "stopReason": "tool_use",
        }
        self.mock_client.get_stop_reason.return_value = "tool_use"
        self.mock_client.parse_tool_use.return_value = [
            ToolUseBlock(id="t1", name="sensitive_tool", input={"value": "x"})
        ]

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            require_confirmation=True,
        )

        result = runner.run(
            "Update something",
            self.mock_session,
            conversation_id=self.mock_conversation.id,
            tool_names=["sensitive_tool"],
        )

        self.assertEqual(result.stop_reason, "confirmation_required")

        mock_save_state.assert_called_once()
        saved_state = mock_save_state.call_args[0][2]

        # Should have: 2 existing + 1 user = 3
        # NOT 5 (which would include duplicated context)
        self.assertEqual(len(saved_state.messages), 3)

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.create_agent_conversation")
    def test_context_length_tracking_first_turn(
        self,
        mock_create_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that context_length is 0 for first turn (no prior context)."""
        mock_create_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        # Track messages passed to converse
        messages_received: list[Any] = []

        def track_converse(*args: Any, **kwargs: Any) -> dict[str, Any]:
            messages_received.extend(kwargs.get("messages", []))
            return {
                "output": {"message": self._make_assistant_message("Response")},
                "stopReason": "end_turn",
            }

        self.mock_client.create_user_message.return_value = self._make_user_message("Hello")
        self.mock_client.converse.side_effect = track_converse
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Response"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        runner.run("Hello", self.mock_session, tool_names=["safe_tool"])

        # First turn should have 1 message sent (just the user message)
        self.assertEqual(len(messages_received), 1)
        self.assertEqual(messages_received[0]["role"], "user")

    @patch("src.agent.runner.save_conversation_state")
    @patch("src.agent.runner.complete_agent_run")
    @patch("src.agent.runner.create_agent_run")
    @patch("src.agent.runner.get_agent_conversation_by_id")
    def test_context_length_tracking_subsequent_turn(
        self,
        mock_get_conv: MagicMock,
        mock_create_run: MagicMock,
        mock_complete_run: MagicMock,
        mock_save_state: MagicMock,
    ) -> None:
        """Test that context_length correctly tracks prior messages."""
        existing_messages = [
            self._make_user_message("First"),
            self._make_assistant_message("First response"),
        ]
        self.mock_conversation.messages_json = existing_messages
        self.mock_conversation.message_count = 2
        mock_get_conv.return_value = self.mock_conversation
        mock_create_run.return_value = self.mock_run

        # Track messages passed to converse
        messages_received: list[Any] = []

        def track_converse(*args: Any, **kwargs: Any) -> dict[str, Any]:
            messages_received.extend(kwargs.get("messages", []))
            return {
                "output": {"message": self._make_assistant_message("Second response")},
                "stopReason": "end_turn",
            }

        self.mock_client.create_user_message.return_value = self._make_user_message("Second")
        self.mock_client.converse.side_effect = track_converse
        self.mock_client.get_stop_reason.return_value = "end_turn"
        self.mock_client.parse_text_response.return_value = "Second response"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        runner.run(
            "Second",
            self.mock_session,
            conversation_id=self.mock_conversation.id,
            tool_names=["safe_tool"],
        )

        # Should receive: 2 context messages + 1 new user message = 3
        self.assertEqual(len(messages_received), 3)

        # Verify saved state only added 2 new messages
        mock_save_state.assert_called_once()
        saved_state = mock_save_state.call_args[0][2]
        self.assertEqual(len(saved_state.messages), 4)


class TestToolTimeout(unittest.TestCase):
    """Tests for tool execution timeout."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()
        self.mock_client = MagicMock()

    def test_tool_times_out_after_configured_seconds(self) -> None:
        """Test that tool execution respects timeout."""

        def slow_handler(args: DummyArgs) -> dict[str, Any]:
            time.sleep(5)  # Sleep longer than timeout
            return {"result": "done"}

        slow_tool = ToolDef(
            name="slow_tool",
            description="A slow tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=slow_handler,
        )
        self.registry.register(slow_tool)

        config = AgentConfig(tool_timeout_seconds=0.5)
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            config=config,
        )

        with self.assertRaises(ToolTimeoutError) as ctx:
            runner._execute_tool(slow_tool, {"value": "test"})

        self.assertEqual(ctx.exception.tool_name, "slow_tool")
        self.assertEqual(ctx.exception.timeout_seconds, 0.5)

    def test_fast_tool_completes_without_timeout(self) -> None:
        """Test that fast tools complete normally."""

        def fast_handler(args: DummyArgs) -> dict[str, Any]:
            return {"result": args.value}

        fast_tool = ToolDef(
            name="fast_tool",
            description="A fast tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=fast_handler,
        )
        self.registry.register(fast_tool)

        config = AgentConfig(tool_timeout_seconds=5.0)
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            config=config,
        )

        result = runner._execute_tool(fast_tool, {"value": "hello"})

        self.assertEqual(result, {"result": "hello"})

    def test_timeout_error_returned_to_llm_with_suggestion(self) -> None:
        """Test that timeout produces error tool result with helpful message."""

        def slow_handler(args: DummyArgs) -> dict[str, Any]:
            time.sleep(5)
            return {"result": "done"}

        slow_tool = ToolDef(
            name="slow_tool",
            description="A slow tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=slow_handler,
        )
        self.registry.register(slow_tool)

        config = AgentConfig(tool_timeout_seconds=0.5)
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            config=config,
        )

        tool_result, tool_call = runner._execute_and_create_tool_call(
            slow_tool,
            "test-id",
            {"value": "test"},
        )

        self.assertTrue(tool_call.is_error)
        self.assertIn("error", tool_result)
        self.assertEqual(tool_result["error_type"], "timeout")
        self.assertIn("suggestion", tool_result)
        self.assertIn("took too long", tool_result["suggestion"])

    def test_config_default_timeout(self) -> None:
        """Test that default config has 30 second timeout."""
        self.assertEqual(DEFAULT_AGENT_CONFIG.tool_timeout_seconds, 30.0)


if __name__ == "__main__":
    unittest.main()
