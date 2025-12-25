"""Tests for AgentRunner."""

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.agent.enums import RiskLevel
from src.agent.exceptions import MaxStepsExceededError, ToolExecutionError
from src.agent.models import AgentRunResult, ConfirmationRequest, ToolDef
from src.agent.registry import ToolRegistry
from src.agent.runner import DEFAULT_MAX_STEPS, DEFAULT_SYSTEM_PROMPT, AgentRunner


class DummyArgs(BaseModel):
    """Dummy argument model for testing."""

    value: str


def dummy_handler(args: DummyArgs) -> dict[str, Any]:
    """Return dummy data for testing."""
    return {"result": args.value}


def error_handler(args: DummyArgs) -> dict[str, Any]:
    """Raise an error for testing."""
    raise RuntimeError("Handler error")


class TestAgentRunner(unittest.TestCase):
    """Tests for AgentRunner."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()

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
            self.assertEqual(runner.max_steps, DEFAULT_MAX_STEPS)
            self.assertTrue(runner.require_confirmation)

    def test_init_with_custom_values(self) -> None:
        """Test initialisation with custom values."""
        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            system_prompt="Custom prompt",
            max_steps=10,
            require_confirmation=False,
        )

        self.assertEqual(runner.system_prompt, "Custom prompt")
        self.assertEqual(runner.max_steps, 10)
        self.assertFalse(runner.require_confirmation)

    def test_run_simple_query_no_tools(self) -> None:
        """Test run when model responds without using tools."""
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

        result = runner.run("Hello", ["safe_tool"])

        self.assertEqual(result.response, "Hi there!")
        self.assertEqual(result.tool_calls, [])
        self.assertEqual(result.steps_taken, 0)
        self.assertEqual(result.stop_reason, "end_turn")

    def test_run_with_safe_tool(self) -> None:
        """Test run where model uses a safe tool."""
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

        result = runner.run("Query something", ["safe_tool"])

        self.assertEqual(result.response, "Done!")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, "safe_tool")
        self.assertEqual(result.tool_calls[0].input_args, {"value": "test"})
        self.assertEqual(result.tool_calls[0].output, {"result": "test"})
        self.assertFalse(result.tool_calls[0].is_error)
        self.assertEqual(result.steps_taken, 1)
        self.assertEqual(result.stop_reason, "end_turn")

    def test_run_sensitive_tool_requires_confirmation(self) -> None:
        """Test that sensitive tools require confirmation."""
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

        result = runner.run("Update something", ["sensitive_tool"])

        self.assertEqual(result.stop_reason, "confirmation_required")
        self.assertIsNotNone(result.confirmation_request)
        self.assertEqual(result.confirmation_request.tool_name, "sensitive_tool")
        self.assertEqual(result.confirmation_request.input_args, {"value": "update"})
        self.assertEqual(result.confirmation_request.tool_use_id, "tool-456")
        self.assertEqual(result.steps_taken, 0)

    def test_run_sensitive_tool_with_confirmation_disabled(self) -> None:
        """Test that sensitive tools run without confirmation when disabled."""
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

        result = runner.run("Update something", ["sensitive_tool"])

        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, "sensitive_tool")

    def test_run_sensitive_tool_with_confirmed_id(self) -> None:
        """Test that sensitive tools run when ID is in confirmed set."""
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
            require_confirmation=True,
        )

        result = runner.run(
            "Update something",
            ["sensitive_tool"],
            confirmed_tool_use_ids={"tool-456"},
        )

        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(len(result.tool_calls), 1)

    def test_run_max_steps_exceeded(self) -> None:
        """Test that max steps limit is enforced."""
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

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
            max_steps=3,
        )

        with self.assertRaises(MaxStepsExceededError) as ctx:
            runner.run("Query", ["safe_tool"])

        self.assertEqual(ctx.exception.max_steps, 3)
        self.assertEqual(ctx.exception.steps_taken, 3)

    def test_run_handles_tool_execution_error(self) -> None:
        """Test that tool execution errors are handled gracefully."""
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

        result = runner.run("Query", ["error_tool"])

        self.assertEqual(len(result.tool_calls), 1)
        self.assertTrue(result.tool_calls[0].is_error)
        self.assertIn("error", result.tool_calls[0].output)

    def test_run_handles_unknown_tool(self) -> None:
        """Test that unknown tool requests are handled gracefully."""
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

        result = runner.run("Query", ["safe_tool"])

        self.assertEqual(len(result.tool_calls), 1)
        self.assertTrue(result.tool_calls[0].is_error)
        self.assertIn("Unknown tool", result.tool_calls[0].output["error"])


class TestAgentRunnerConfirmation(unittest.TestCase):
    """Tests for AgentRunner confirmation flow."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()

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

    def test_run_with_confirmation_user_confirms(self) -> None:
        """Test confirmation flow when user confirms."""
        # Create a pending result
        pending_result = AgentRunResult(
            response="",
            tool_calls=[],
            steps_taken=0,
            stop_reason="confirmation_required",
            confirmation_request=ConfirmationRequest(
                tool_name="sensitive_tool",
                tool_description="A sensitive test tool",
                input_args={"value": "test"},
                action_summary="A sensitive test tool\nArguments: value='test'",
                tool_use_id="tool-456",
            ),
        )

        # Set up mock for re-run
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
                                "input": {"value": "test"},
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
            {"toolUseId": "tool-456", "name": "sensitive_tool", "input": {"value": "test"}}
        ]
        self.mock_client.create_tool_result_message.return_value = {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "tool-456"}}],
        }
        self.mock_client.parse_text_response.return_value = "Updated!"

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run_with_confirmation(
            user_message="Update something",
            pending_result=pending_result,
            confirmed=True,
            tool_names=["sensitive_tool"],
        )

        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(result.response, "Updated!")

    def test_run_with_confirmation_user_declines(self) -> None:
        """Test confirmation flow when user declines."""
        pending_result = AgentRunResult(
            response="",
            tool_calls=[],
            steps_taken=0,
            stop_reason="confirmation_required",
            confirmation_request=ConfirmationRequest(
                tool_name="sensitive_tool",
                tool_description="A sensitive test tool",
                input_args={"value": "test"},
                action_summary="A sensitive test tool\nArguments: value='test'",
                tool_use_id="tool-456",
            ),
        )

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        result = runner.run_with_confirmation(
            user_message="Update something",
            pending_result=pending_result,
            confirmed=False,
            tool_names=["sensitive_tool"],
        )

        self.assertEqual(result.stop_reason, "user_cancelled")
        self.assertEqual(result.response, "Action cancelled by user.")

    def test_run_with_confirmation_invalid_pending_result(self) -> None:
        """Test that invalid pending result raises ValueError."""
        pending_result = AgentRunResult(
            response="Done",
            tool_calls=[],
            steps_taken=0,
            stop_reason="end_turn",
        )

        runner = AgentRunner(
            registry=self.registry,
            client=self.mock_client,
        )

        with self.assertRaises(ValueError) as ctx:
            runner.run_with_confirmation(
                user_message="Update something",
                pending_result=pending_result,
                confirmed=True,
                tool_names=["sensitive_tool"],
            )

        self.assertIn("does not require confirmation", str(ctx.exception))


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
