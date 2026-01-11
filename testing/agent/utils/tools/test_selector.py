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

        # Register test tools with domain tags
        self.query_tool = ToolDef(
            name="query_items",
            description="Query items from the database",
            tags=frozenset({"domain:items", "query", "read"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.delete_tool = ToolDef(
            name="delete_item",
            description="Delete an item from the database",
            tags=frozenset({"domain:items", "delete", "write"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.query_tool)
        self.registry.register(self.delete_tool)

        self.selector = ToolSelector(
            registry=self.registry,
            client=self.mock_client,
            max_tools=10,
        )

    def test_select_with_ai_success(self) -> None:
        """Test successful AI-based domain selection."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = (
            '{"domains": ["domain:items"], "reasoning": "User wants to work with items"}'
        )

        result = self.selector.select("Show me all items")

        # Should return all tools for the domain
        self.assertIn("query_items", result.tool_names)
        self.assertIn("delete_item", result.tool_names)
        self.assertEqual(result.domains, ["domain:items"])
        self.assertEqual(result.reasoning, "User wants to work with items")
        self.mock_client.converse.assert_called_once()

    def test_select_filters_invalid_domains(self) -> None:
        """Test that invalid domain tags are filtered out."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = (
            '{"domains": ["domain:items", "domain:nonexistent"], "reasoning": "test"}'
        )

        result = self.selector.select("Show me all items")

        self.assertEqual(result.domains, ["domain:items"])

    def test_select_respects_max_tools(self) -> None:
        """Test that selection respects the max_tools limit via domain pruning."""
        # Create a registry with multiple domains
        registry = ToolRegistry()

        # Add 6 tools in domain A
        for i in range(6):
            registry.register(
                ToolDef(
                    name=f"tool_a_{i}",
                    description=f"Domain A tool {i}",
                    tags=frozenset({"domain:domain_a"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        # Add 6 tools in domain B
        for i in range(6):
            registry.register(
                ToolDef(
                    name=f"tool_b_{i}",
                    description=f"Domain B tool {i}",
                    tags=frozenset({"domain:domain_b"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        selector = ToolSelector(
            registry=registry,
            client=self.mock_client,
            max_tools=10,
        )

        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        # Try to select both domains (12 tools total, but max is 10)
        self.mock_client.parse_text_response.return_value = json.dumps(
            {"domains": ["domain:domain_a", "domain:domain_b"], "reasoning": "test"}
        )

        result = selector.select("Use all tools")

        # Should only include first domain (6 tools) since adding second would exceed limit
        self.assertEqual(len(result.tool_names), 6)
        self.assertEqual(result.domains, ["domain:domain_a"])

    def test_select_deduplicates_domains(self) -> None:
        """Test that duplicate domains are removed while preserving order."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        # LLM mistakenly returns the same domain multiple times
        self.mock_client.parse_text_response.return_value = json.dumps(
            {
                "domains": [
                    "domain:items",
                    "domain:items",
                    "domain:items",
                ],
                "reasoning": "User wants to work with items",
            }
        )

        result = self.selector.select("Show me items")

        # Should deduplicate to unique domains
        self.assertEqual(result.domains, ["domain:items"])

    def test_select_handles_markdown_code_block(self) -> None:
        """Test parsing response wrapped in markdown code block."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = (
            '```json\n{"domains": ["domain:items"], "reasoning": "test"}\n```'
        )

        result = self.selector.select("Show items")

        self.assertEqual(result.domains, ["domain:items"])

    def test_select_empty_registry(self) -> None:
        """Test selection with empty registry."""
        empty_registry = ToolRegistry()
        selector = ToolSelector(registry=empty_registry, client=self.mock_client)

        result = selector.select("Do something")

        self.assertEqual(result.tool_names, [])
        self.assertEqual(result.domains, [])
        self.assertIn("No domains available", result.reasoning)
        self.mock_client.converse.assert_not_called()

    def test_select_falls_back_on_bedrock_error(self) -> None:
        """Test fallback to keyword matching when Bedrock fails."""
        self.mock_client.create_user_message.return_value = {
            "role": "user",
            "content": [{"text": "test"}],
        }
        self.mock_client.converse.side_effect = BedrockClientError("API error")

        result = self.selector.select("show me all items")

        # Fallback should match 'items' to 'domain:items'
        self.assertIn("domain:items", result.domains)
        self.assertIn("query_items", result.tool_names)
        self.assertIn("fallback", result.reasoning)

    def test_fallback_domain_selection_matches_domain_name(self) -> None:
        """Test that fallback selection matches domain names."""
        available_domains = {"domain:items", "domain:tasks"}

        result_domains, reasoning = self.selector._fallback_domain_selection(
            "I need to query items", available_domains
        )

        self.assertIn("domain:items", result_domains)
        self.assertIn("fallback", reasoning)

    def test_fallback_domain_selection_matches_singular(self) -> None:
        """Test that fallback matches singular form of domain names."""
        available_domains = {"domain:items", "domain:tasks"}

        # 'item' (singular) should match 'items' domain
        result_domains, _ = self.selector._fallback_domain_selection(
            "delete the item", available_domains
        )

        self.assertIn("domain:items", result_domains)

    def test_select_by_tags(self) -> None:
        """Test deterministic tag-based selection."""
        result = self.selector.select_by_tags({"query"})

        self.assertEqual(result.tool_names, ["query_items"])
        self.assertIn("tags", result.reasoning)

    def test_select_by_tags_includes_domain(self) -> None:
        """Test that tag selection includes domain info."""
        result = self.selector.select_by_tags({"domain:items"})

        self.assertIn("query_items", result.tool_names)
        self.assertIn("delete_item", result.tool_names)
        self.assertIn("domain:items", result.domains)

    def test_parse_domain_response_invalid_json(self) -> None:
        """Test that invalid JSON raises ToolSelectionError."""
        with self.assertRaises(ToolSelectionError):
            self.selector._parse_domain_response("not json", {"domain:items"})

    def test_parse_domain_response_missing_keys(self) -> None:
        """Test handling of response with missing keys."""
        # Should handle gracefully with defaults
        domains, reasoning = self.selector._parse_domain_response("{}", {"domain:items"})

        self.assertEqual(domains, [])
        self.assertEqual(reasoning, "")

    def test_parse_domain_response_domains_not_list(self) -> None:
        """Test that non-list domains value raises ToolSelectionError."""
        # LLM might return a string instead of a list
        response = '{"domains": "domain:items", "reasoning": "test"}'

        with self.assertRaises(ToolSelectionError) as context:
            self.selector._parse_domain_response(response, {"domain:items"})

        self.assertIn("Expected 'domains' to be a list", str(context.exception))
        self.assertIn("str", str(context.exception))

    def test_tools_to_domains(self) -> None:
        """Test extracting domains from tool names."""
        domains = self.selector._tools_to_domains(["query_items", "delete_item"])

        self.assertEqual(domains, ["domain:items"])

    def test_tools_to_domains_preserves_order(self) -> None:
        """Test that tools_to_domains preserves first occurrence order."""
        # Add tools in a second domain
        self.registry.register(
            ToolDef(
                name="create_task",
                description="Create task",
                tags=frozenset({"domain:tasks"}),
                args_model=DummyArgs,
                handler=dummy_handler,
            )
        )

        domains = self.selector._tools_to_domains(["query_items", "create_task", "delete_item"])

        self.assertEqual(domains, ["domain:items", "domain:tasks"])

    def test_merge_domains_by_recency(self) -> None:
        """Test that merge puts existing domains first for cache stability."""
        intent = ["domain:tasks"]
        existing = ["domain:items", "domain:goals"]

        merged = self.selector._merge_domains_by_recency(intent, existing)

        # Existing domains first (cached), then new intent domains
        self.assertEqual(merged, ["domain:items", "domain:goals", "domain:tasks"])

    def test_merge_domains_deduplicates(self) -> None:
        """Test that merge removes duplicates, keeping existing domain position."""
        intent = ["domain:items"]
        existing = ["domain:items", "domain:tasks"]

        merged = self.selector._merge_domains_by_recency(intent, existing)

        # items already in existing, so it stays in its existing position
        self.assertEqual(merged, ["domain:items", "domain:tasks"])

    def test_prune_domains_to_limit(self) -> None:
        """Test that prune drops oldest domains."""
        # Create registry with known tool counts
        registry = ToolRegistry()

        # Domain A: 4 tools
        for i in range(4):
            registry.register(
                ToolDef(
                    name=f"tool_a_{i}",
                    description=f"A {i}",
                    tags=frozenset({"domain:a"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        # Domain B: 4 tools
        for i in range(4):
            registry.register(
                ToolDef(
                    name=f"tool_b_{i}",
                    description=f"B {i}",
                    tags=frozenset({"domain:b"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        # Domain C: 4 tools
        for i in range(4):
            registry.register(
                ToolDef(
                    name=f"tool_c_{i}",
                    description=f"C {i}",
                    tags=frozenset({"domain:c"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        selector = ToolSelector(registry=registry, max_tools=10)

        # Try to include all three domains (12 tools, but max is 10)
        domains = ["domain:a", "domain:b", "domain:c"]
        pruned = selector._prune_domains_to_limit(domains)

        # Should keep first two domains (8 tools), drop third
        self.assertEqual(pruned, ["domain:a", "domain:b"])

    def test_expand_domains_to_tools(self) -> None:
        """Test expanding domains to tool names."""
        tools = self.selector._expand_domains_to_tools(["domain:items"])

        self.assertIn("query_items", tools)
        self.assertIn("delete_item", tools)
        self.assertEqual(len(tools), 2)


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
            tags=frozenset({"domain:test"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        registry.register(tool)

        mock_create_msg.return_value = {"role": "user", "content": [{"text": "test"}]}
        mock_converse.return_value = {"output": {"message": {}}}
        mock_parse.return_value = '{"domains": ["domain:test"], "reasoning": "test"}'

        selector = ToolSelector(registry=registry)
        result = selector.select("Test query")

        self.assertEqual(result.tool_names, ["test"])
        self.assertEqual(result.domains, ["domain:test"])


if __name__ == "__main__":
    unittest.main()
