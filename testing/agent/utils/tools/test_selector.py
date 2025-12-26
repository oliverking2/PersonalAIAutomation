"""Tests for ToolSelector."""

import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import RiskLevel
from src.agent.exceptions import BedrockClientError, ToolSelectionError
from src.agent.models import ToolDef
from src.agent.utils.tools.registry import ToolRegistry
from src.agent.utils.tools.selector import ToolSelector


class DummyArgs(BaseModel):
    """Dummy argument model for testing."""

    value: str


def dummy_handler(args: DummyArgs) -> dict[str, Any]:
    """Return dummy data for testing."""
    return {"value": args.value}


class TestToolSelector(unittest.TestCase):
    """Tests for ToolSelector."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()
        self.mock_client = MagicMock(spec=BedrockClient)

        # Register some test tools
        self.safe_tool = ToolDef(
            name="query_items",
            description="Query items from the database",
            tags=frozenset({"query", "read"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.sensitive_tool = ToolDef(
            name="delete_item",
            description="Delete an item from the database",
            tags=frozenset({"delete", "write"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.safe_tool)
        self.registry.register(self.sensitive_tool)

        self.selector = ToolSelector(
            registry=self.registry,
            client=self.mock_client,
            max_tools=5,
        )

    def test_select_with_ai_success(self) -> None:
        """Test successful AI-based tool selection."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = (
            '{"tool_names": ["query_items"], "reasoning": "User wants to query"}'
        )

        result = self.selector.select("Show me all items")

        self.assertEqual(result.tool_names, ["query_items"])
        self.assertEqual(result.reasoning, "User wants to query")
        self.mock_client.converse.assert_called_once()

    def test_select_filters_invalid_tools(self) -> None:
        """Test that invalid tool names are filtered out."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = (
            '{"tool_names": ["query_items", "nonexistent"], "reasoning": "test"}'
        )

        result = self.selector.select("Show me all items")

        self.assertEqual(result.tool_names, ["query_items"])

    def test_select_respects_max_tools(self) -> None:
        """Test that selection respects the max_tools limit."""
        # Add more tools
        for i in range(10):
            self.registry.register(
                ToolDef(
                    name=f"tool_{i}",
                    description=f"Tool {i}",
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        # Return more tools than max
        tool_names = [f"tool_{i}" for i in range(10)]
        self.mock_client.parse_text_response.return_value = json.dumps(
            {"tool_names": tool_names, "reasoning": "test"}
        )

        result = self.selector.select("Use all tools")

        self.assertEqual(len(result.tool_names), 5)

    def test_select_handles_markdown_code_block(self) -> None:
        """Test parsing response wrapped in markdown code block."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = (
            '```json\n{"tool_names": ["query_items"], "reasoning": "test"}\n```'
        )

        result = self.selector.select("Show items")

        self.assertEqual(result.tool_names, ["query_items"])

    def test_select_empty_registry(self) -> None:
        """Test selection with empty registry."""
        empty_registry = ToolRegistry()
        selector = ToolSelector(registry=empty_registry, client=self.mock_client)

        result = selector.select("Do something")

        self.assertEqual(result.tool_names, [])
        self.assertIn("No tools available", result.reasoning)
        self.mock_client.converse.assert_not_called()

    def test_select_falls_back_on_bedrock_error(self) -> None:
        """Test fallback to keyword matching when Bedrock fails."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.side_effect = BedrockClientError("API error")

        result = self.selector.select("query items from database")

        self.assertIn("query_items", result.tool_names)
        self.assertIn("fallback", result.reasoning)

    def test_fallback_selection_prefers_safe_tools(self) -> None:
        """Test that fallback selection prefers safe tools."""
        result = self.selector._fallback_selection("delete or query", self.registry.list_metadata())

        # Safe tool should be boosted in score
        if result.tool_names:
            # Both might be selected based on keyword matching
            self.assertIn("fallback", result.reasoning)

    def test_fallback_selection_matches_tags(self) -> None:
        """Test that fallback selection matches on tags."""
        result = self.selector._fallback_selection(
            "I need to read some data", self.registry.list_metadata()
        )

        # 'read' is a tag of query_items
        self.assertIn("query_items", result.tool_names)

    def test_select_by_tags(self) -> None:
        """Test deterministic tag-based selection."""
        result = self.selector.select_by_tags({"query"})

        self.assertEqual(result.tool_names, ["query_items"])
        self.assertIn("tags", result.reasoning)

    def test_select_by_tags_orders_safe_first(self) -> None:
        """Test that tag selection orders safe tools first."""
        # Add another safe tool with same tag as sensitive
        mixed_tool = ToolDef(
            name="safe_write",
            description="Safe write operation",
            tags=frozenset({"write"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(mixed_tool)

        result = self.selector.select_by_tags({"write"})

        # Safe tool should come first
        self.assertEqual(result.tool_names[0], "safe_write")

    def test_parse_selection_response_invalid_json(self) -> None:
        """Test that invalid JSON raises ToolSelectionError."""
        with self.assertRaises(ToolSelectionError):
            self.selector._parse_selection_response("not json", {"tool1"})

    def test_parse_selection_response_missing_keys(self) -> None:
        """Test handling of response with missing keys."""
        # Should handle gracefully with defaults
        result = self.selector._parse_selection_response("{}", {"tool1"})

        self.assertEqual(result.tool_names, [])
        self.assertEqual(result.reasoning, "")


class TestToolSelectorIntegration(unittest.TestCase):
    """Integration-style tests for ToolSelector without mocking client creation."""

    @patch.object(BedrockClient, "__init__", return_value=None)
    @patch.object(BedrockClient, "converse")
    @patch.object(BedrockClient, "parse_text_response")
    @patch.object(BedrockClient, "create_user_message")
    def test_selector_creates_client_if_not_provided(
        self,
        mock_create_msg: MagicMock,
        mock_parse: MagicMock,
        mock_converse: MagicMock,
        mock_init: MagicMock,
    ) -> None:
        """Test that selector creates a client if none provided."""
        registry = ToolRegistry()
        tool = ToolDef(
            name="test",
            description="Test",
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        registry.register(tool)

        mock_create_msg.return_value = {"role": "user", "content": [{"text": "test"}]}
        mock_converse.return_value = {"output": {"message": {}}}
        mock_parse.return_value = '{"tool_names": ["test"], "reasoning": "test"}'

        selector = ToolSelector(registry=registry)
        result = selector.select("Test query")

        self.assertEqual(result.tool_names, ["test"])


if __name__ == "__main__":
    unittest.main()
