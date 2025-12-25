"""Tests for ToolRegistry."""

import unittest
from typing import Any

from pydantic import BaseModel

from src.agent.enums import RiskLevel
from src.agent.exceptions import DuplicateToolError, ToolNotFoundError
from src.agent.models import ToolDef
from src.agent.registry import ToolRegistry


class DummyArgs(BaseModel):
    """Dummy argument model for testing."""

    value: str


def dummy_handler(args: DummyArgs) -> dict[str, Any]:
    """Return dummy data for testing."""
    return {"value": args.value}


class TestToolRegistry(unittest.TestCase):
    """Tests for ToolRegistry."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()
        self.tool = ToolDef(
            name="test_tool",
            description="A test tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )

    def test_register_tool(self) -> None:
        """Test registering a tool."""
        self.registry.register(self.tool)

        self.assertIn("test_tool", self.registry)
        self.assertEqual(len(self.registry), 1)

    def test_register_duplicate_raises_error(self) -> None:
        """Test that registering a duplicate tool raises an error."""
        self.registry.register(self.tool)

        with self.assertRaises(DuplicateToolError) as ctx:
            self.registry.register(self.tool)

        self.assertEqual(ctx.exception.tool_name, "test_tool")

    def test_get_tool(self) -> None:
        """Test retrieving a tool by name."""
        self.registry.register(self.tool)

        retrieved = self.registry.get("test_tool")

        self.assertEqual(retrieved.name, "test_tool")

    def test_get_missing_tool_raises_error(self) -> None:
        """Test that getting a missing tool raises an error."""
        with self.assertRaises(ToolNotFoundError) as ctx:
            self.registry.get("nonexistent")

        self.assertEqual(ctx.exception.tool_name, "nonexistent")

    def test_get_many(self) -> None:
        """Test retrieving multiple tools."""
        tool2 = ToolDef(
            name="tool2",
            description="Another tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(tool2)

        tools = self.registry.get_many(["test_tool", "tool2"])

        self.assertEqual(len(tools), 2)
        self.assertEqual(tools[0].name, "test_tool")
        self.assertEqual(tools[1].name, "tool2")

    def test_list_all(self) -> None:
        """Test listing all tools."""
        self.registry.register(self.tool)

        all_tools = self.registry.list_all()

        self.assertEqual(len(all_tools), 1)
        self.assertEqual(all_tools[0].name, "test_tool")

    def test_list_metadata(self) -> None:
        """Test listing tool metadata."""
        self.registry.register(self.tool)

        metadata = self.registry.list_metadata()

        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].name, "test_tool")
        self.assertEqual(metadata[0].description, "A test tool")
        self.assertEqual(metadata[0].tags, frozenset({"test"}))
        self.assertEqual(metadata[0].risk_level, RiskLevel.SAFE)

    def test_filter_by_tags(self) -> None:
        """Test filtering tools by tags."""
        tool2 = ToolDef(
            name="tool2",
            description="Another tool",
            tags=frozenset({"other"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(tool2)

        filtered = self.registry.filter_by_tags({"test"})

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].name, "test_tool")

    def test_filter_by_risk_level(self) -> None:
        """Test filtering tools by risk level."""
        sensitive_tool = ToolDef(
            name="sensitive",
            description="Sensitive tool",
            risk_level=RiskLevel.SENSITIVE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(sensitive_tool)

        safe_tools = self.registry.filter_by_risk_level(RiskLevel.SAFE)
        sensitive_tools = self.registry.filter_by_risk_level(RiskLevel.SENSITIVE)

        self.assertEqual(len(safe_tools), 1)
        self.assertEqual(safe_tools[0].name, "test_tool")
        self.assertEqual(len(sensitive_tools), 1)
        self.assertEqual(sensitive_tools[0].name, "sensitive")

    def test_to_bedrock_tool_config(self) -> None:
        """Test generating Bedrock tool config."""
        self.registry.register(self.tool)

        config = self.registry.to_bedrock_tool_config(["test_tool"])

        self.assertIn("tools", config)
        self.assertEqual(len(config["tools"]), 1)
        self.assertIn("toolSpec", config["tools"][0])

    def test_contains(self) -> None:
        """Test the __contains__ method."""
        self.registry.register(self.tool)

        self.assertTrue("test_tool" in self.registry)
        self.assertFalse("other" in self.registry)

    def test_len(self) -> None:
        """Test the __len__ method."""
        self.assertEqual(len(self.registry), 0)

        self.registry.register(self.tool)
        self.assertEqual(len(self.registry), 1)


if __name__ == "__main__":
    unittest.main()
