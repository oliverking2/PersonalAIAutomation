"""Tests for memory tool definitions."""

import unittest
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from src.agent.enums import MemoryCategory, RiskLevel
from src.agent.tools.memory import (
    ADD_TO_MEMORY_TOOL,
    UPDATE_MEMORY_TOOL,
    AddToMemoryArgs,
    UpdateMemoryArgs,
    get_memory_tools,
)
from src.api.client import InternalAPIClientError


class TestMemoryToolDefinitions(unittest.TestCase):
    """Tests for memory tool definitions."""

    def test_get_memory_tools_returns_two_tools(self) -> None:
        """Test that get_memory_tools returns both tools."""
        tools = get_memory_tools()

        self.assertEqual(len(tools), 2)
        tool_names = {t.name for t in tools}
        self.assertEqual(tool_names, {"add_to_memory", "update_memory"})

    def test_tools_are_safe(self) -> None:
        """Test that both memory tools are marked as safe."""
        tools = get_memory_tools()

        for tool in tools:
            self.assertEqual(tool.risk_level, RiskLevel.SAFE)

    def test_tools_have_system_tag(self) -> None:
        """Test that all tools have the system tag."""
        tools = get_memory_tools()

        for tool in tools:
            self.assertIn("system", tool.tags)

    def test_tools_have_memory_tag(self) -> None:
        """Test that all tools have the memory tag."""
        tools = get_memory_tools()

        for tool in tools:
            self.assertIn("memory", tool.tags)

    def test_tools_generate_valid_json_schema(self) -> None:
        """Test that all tools generate valid JSON schemas."""
        tools = get_memory_tools()

        for tool in tools:
            schema = tool.to_json_schema()
            self.assertIn("properties", schema)
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")


class TestAddToMemoryArgs(unittest.TestCase):
    """Tests for AddToMemoryArgs validation."""

    def test_valid_args(self) -> None:
        """Test valid add_to_memory arguments."""
        args = AddToMemoryArgs(
            content="Alec is my boss at TechCorp",
            category=MemoryCategory.PERSON,
            subject="Alec",
        )

        self.assertEqual(args.content, "Alec is my boss at TechCorp")
        self.assertEqual(args.category, MemoryCategory.PERSON)
        self.assertEqual(args.subject, "Alec")

    def test_subject_is_optional(self) -> None:
        """Test that subject is optional."""
        args = AddToMemoryArgs(
            content="I prefer Friday due dates",
            category=MemoryCategory.PREFERENCE,
        )

        self.assertIsNone(args.subject)

    def test_content_min_length(self) -> None:
        """Test that content must be at least 5 characters."""
        with self.assertRaises(ValidationError):
            AddToMemoryArgs(content="Hi", category=MemoryCategory.CONTEXT)

    def test_content_max_length(self) -> None:
        """Test that content cannot exceed 500 characters."""
        with self.assertRaises(ValidationError):
            AddToMemoryArgs(content="x" * 501, category=MemoryCategory.CONTEXT)


class TestUpdateMemoryArgs(unittest.TestCase):
    """Tests for UpdateMemoryArgs validation."""

    def test_valid_args(self) -> None:
        """Test valid update_memory arguments."""
        args = UpdateMemoryArgs(
            memory_id="abc12345",
            content="Sarah works on the Design team",
        )

        self.assertEqual(args.memory_id, "abc12345")
        self.assertEqual(args.content, "Sarah works on the Design team")

    def test_content_min_length(self) -> None:
        """Test that content must be at least 5 characters."""
        with self.assertRaises(ValidationError):
            UpdateMemoryArgs(memory_id="abc12345", content="Hi")


class TestAddToMemoryHandler(unittest.TestCase):
    """Tests for add_to_memory handler."""

    @patch("src.agent.tools.memory.InternalAPIClient")
    def test_add_to_memory_success(self, mock_client_class: MagicMock) -> None:
        """Test successful memory creation."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.post.return_value = {
            "id": "mem12345",
            "content": "Alec is my boss",
            "category": "person",
            "subject": "Alec",
        }

        args = AddToMemoryArgs(
            content="Alec is my boss",
            category=MemoryCategory.PERSON,
            subject="Alec",
        )

        result = ADD_TO_MEMORY_TOOL.handler(args)

        self.assertTrue(result["created"])
        self.assertEqual(result["id"], "mem12345")
        self.assertEqual(result["content"], "Alec is my boss")

    @patch("src.agent.tools.memory.InternalAPIClient")
    def test_add_to_memory_duplicate_subject(self, mock_client_class: MagicMock) -> None:
        """Test handling of duplicate subject."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.post.side_effect = InternalAPIClientError(
            "Memory with subject 'Alec' already exists", status_code=HTTPStatus.CONFLICT
        )

        args = AddToMemoryArgs(
            content="Alec is my manager",
            category=MemoryCategory.PERSON,
            subject="Alec",
        )

        result = ADD_TO_MEMORY_TOOL.handler(args)

        self.assertFalse(result["created"])
        self.assertEqual(result["error"], "duplicate_subject")


class TestUpdateMemoryHandler(unittest.TestCase):
    """Tests for update_memory handler."""

    @patch("src.agent.tools.memory.InternalAPIClient")
    def test_update_memory_success(self, mock_client_class: MagicMock) -> None:
        """Test successful memory update."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.patch.return_value = {
            "id": "mem12345",
            "content": "Sarah works on the Design team",
            "version": 2,
        }

        args = UpdateMemoryArgs(
            memory_id="mem12345",
            content="Sarah works on the Design team",
        )

        result = UPDATE_MEMORY_TOOL.handler(args)

        self.assertTrue(result["updated"])
        self.assertEqual(result["id"], "mem12345")
        self.assertEqual(result["version"], 2)

    @patch("src.agent.tools.memory.InternalAPIClient")
    def test_update_memory_with_subject_change(self, mock_client_class: MagicMock) -> None:
        """Test updating memory with subject change."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.patch.return_value = {
            "id": "mem12345",
            "content": "Seabrook is my boss",
            "subject": "Seabrook",
            "version": 2,
        }

        args = UpdateMemoryArgs(
            memory_id="mem12345",
            content="Seabrook is my boss",
            subject="Seabrook",
        )

        result = UPDATE_MEMORY_TOOL.handler(args)

        self.assertTrue(result["updated"])
        self.assertEqual(result["id"], "mem12345")
        # Verify subject was included in request
        mock_client.patch.assert_called_once_with(
            "/memory/mem12345",
            json={"content": "Seabrook is my boss", "subject": "Seabrook"},
        )

    @patch("src.agent.tools.memory.InternalAPIClient")
    def test_update_memory_not_found(self, mock_client_class: MagicMock) -> None:
        """Test handling of memory not found."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.patch.side_effect = InternalAPIClientError(
            "Memory not found: notfound1", status_code=HTTPStatus.NOT_FOUND
        )

        args = UpdateMemoryArgs(
            memory_id="notfound1",
            content="New content for this memory",
        )

        result = UPDATE_MEMORY_TOOL.handler(args)

        self.assertFalse(result["updated"])
        self.assertEqual(result["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
