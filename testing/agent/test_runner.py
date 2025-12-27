"""Tests for AgentRunner."""

import unittest
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.agent.enums import RiskLevel
from src.agent.exceptions import MaxStepsExceededError, ToolExecutionError
from src.agent.models import ToolDef
from src.agent.runner import DEFAULT_SYSTEM_PROMPT, AgentRunner
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
            {"toolUseId": "tool-123", "name": "safe_tool", "input": {"value": "test"}}
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
    ) -> None:
        """Test that sensitive tools require confirmation."""
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

        self.mock_client.converse.return_value = tool_response
        self.mock_client.get_stop_reason.return_value = "tool_use"
        self.mock_client.parse_tool_use.return_value = [
            {"toolUseId": "tool-456", "name": "sensitive_tool", "input": {"value": "update"}}
        ]

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            require_confirmation=True,
        )

        result = runner.run("Update something", self.mock_session, tool_names=["sensitive_tool"])

        self.assertEqual(result.stop_reason, "confirmation_required")
        self.assertIsNotNone(result.confirmation_request)
        self.assertEqual(result.confirmation_request.tool_name, "sensitive_tool")
        self.assertEqual(result.confirmation_request.input_args, {"value": "update"})
        self.assertEqual(result.confirmation_request.tool_use_id, "tool-456")
        self.assertEqual(result.steps_taken, 0)

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
            {"toolUseId": "tool-456", "name": "sensitive_tool", "input": {"value": "update"}}
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
            {"toolUseId": "tool-x", "name": "safe_tool", "input": {"value": "test"}}
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
            {"toolUseId": "tool-err", "name": "error_tool", "input": {"value": "test"}}
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
            {"toolUseId": "tool-unknown", "name": "nonexistent_tool", "input": {"value": "test"}}
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
            {"toolUseId": "tool-1", "name": "safe_tool", "input": {"value": "first"}},
            {"toolUseId": "tool-2", "name": "safe_tool", "input": {"value": "second"}},
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


if __name__ == "__main__":
    unittest.main()
