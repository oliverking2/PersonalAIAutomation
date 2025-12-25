"""Tests for agent models."""

import unittest
from typing import Any

from pydantic import BaseModel

from src.agent.enums import RiskLevel
from src.agent.models import ToolDef, ToolMetadata, ToolSelectionResult


class DummyArgs(BaseModel):
    """Dummy argument model for testing."""

    name: str
    count: int = 1


def dummy_handler(args: DummyArgs) -> dict[str, Any]:
    """Return dummy data for testing."""
    return {"name": args.name, "count": args.count}


class TestToolDef(unittest.TestCase):
    """Tests for ToolDef model."""

    def test_create_tool_def(self) -> None:
        """Test creating a valid ToolDef."""
        tool = ToolDef(
            name="test_tool",
            description="A test tool",
            tags=frozenset({"test", "demo"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        self.assertEqual(tool.name, "test_tool")
        self.assertEqual(tool.description, "A test tool")
        self.assertEqual(tool.tags, frozenset({"test", "demo"}))
        self.assertEqual(tool.risk_level, RiskLevel.SAFE)

    def test_tool_def_defaults(self) -> None:
        """Test ToolDef default values."""
        tool = ToolDef(
            name="minimal",
            description="Minimal tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        self.assertEqual(tool.tags, frozenset())
        self.assertEqual(tool.risk_level, RiskLevel.SAFE)

    def test_to_json_schema(self) -> None:
        """Test JSON schema generation."""
        tool = ToolDef(
            name="test_tool",
            description="A test tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        schema = tool.to_json_schema()

        self.assertIn("properties", schema)
        self.assertIn("name", schema["properties"])
        self.assertIn("count", schema["properties"])
        self.assertNotIn("title", schema)

    def test_to_bedrock_tool_spec(self) -> None:
        """Test Bedrock tool spec generation."""
        tool = ToolDef(
            name="test_tool",
            description="A test tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        spec = tool.to_bedrock_tool_spec()

        self.assertIn("toolSpec", spec)
        self.assertEqual(spec["toolSpec"]["name"], "test_tool")
        self.assertEqual(spec["toolSpec"]["description"], "A test tool")
        self.assertIn("inputSchema", spec["toolSpec"])
        self.assertIn("json", spec["toolSpec"]["inputSchema"])

    def test_tool_def_is_frozen(self) -> None:
        """Test that ToolDef is immutable."""
        tool = ToolDef(
            name="test_tool",
            description="A test tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )

        with self.assertRaises(Exception):
            tool.name = "new_name"  # type: ignore[misc]


class TestToolMetadata(unittest.TestCase):
    """Tests for ToolMetadata model."""

    def test_create_metadata(self) -> None:
        """Test creating ToolMetadata."""
        metadata = ToolMetadata(
            name="tool1",
            description="Description",
            tags=frozenset({"tag1"}),
            risk_level=RiskLevel.SENSITIVE,
        )

        self.assertEqual(metadata.name, "tool1")
        self.assertEqual(metadata.description, "Description")
        self.assertEqual(metadata.risk_level, RiskLevel.SENSITIVE)

    def test_metadata_is_frozen(self) -> None:
        """Test that ToolMetadata is immutable."""
        metadata = ToolMetadata(
            name="tool1",
            description="Description",
            tags=frozenset(),
            risk_level=RiskLevel.SAFE,
        )

        with self.assertRaises(Exception):
            metadata.name = "new_name"  # type: ignore[misc]


class TestToolSelectionResult(unittest.TestCase):
    """Tests for ToolSelectionResult model."""

    def test_create_result(self) -> None:
        """Test creating ToolSelectionResult."""
        result = ToolSelectionResult(
            tool_names=["tool1", "tool2"],
            reasoning="Selected based on intent",
        )

        self.assertEqual(result.tool_names, ["tool1", "tool2"])
        self.assertEqual(result.reasoning, "Selected based on intent")

    def test_result_defaults(self) -> None:
        """Test ToolSelectionResult default values."""
        result = ToolSelectionResult()

        self.assertEqual(result.tool_names, [])
        self.assertEqual(result.reasoning, "")


if __name__ == "__main__":
    unittest.main()
