"""Tests for reading list tool definitions."""

import unittest
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.models import AgentReadingItemCreateArgs
from src.agent.tools.reading_list import READING_LIST_TOOL_CONFIG, get_reading_list_tools
from src.api.notion.reading_list.models import ReadingItemCreateRequest, ReadingQueryRequest
from src.notion.enums import Priority, ReadingCategory, ReadingStatus, ReadingType


class TestReadingListToolDefinitions(unittest.TestCase):
    """Tests for reading list tool definitions."""

    def test_get_reading_list_tools_returns_four_tools(self) -> None:
        """Test that get_reading_list_tools returns all four tools."""
        tools = get_reading_list_tools()

        self.assertEqual(len(tools), 4)
        tool_names = {t.name for t in tools}
        self.assertEqual(
            tool_names,
            {
                "query_reading_list",
                "get_reading_item",
                "create_reading_list",
                "update_reading_item",
            },
        )

    def test_safe_tools(self) -> None:
        """Test that query, get, and create tools are marked as safe."""
        tools = get_reading_list_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_reading_list"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_reading_item"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["create_reading_list"].risk_level, RiskLevel.SAFE)

    def test_sensitive_tools(self) -> None:
        """Test that update tool is marked as sensitive."""
        tools = get_reading_list_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["update_reading_item"].risk_level, RiskLevel.SENSITIVE)

    def test_tools_have_reading_tag(self) -> None:
        """Test that all tools have the reading tag."""
        tools = get_reading_list_tools()

        for tool in tools:
            self.assertIn("reading", tool.tags)

    def test_tools_generate_valid_json_schema(self) -> None:
        """Test that all tools generate valid JSON schemas."""
        tools = get_reading_list_tools()

        for tool in tools:
            schema = tool.to_json_schema()
            self.assertIn("properties", schema)
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")


class TestReadingListToolConfig(unittest.TestCase):
    """Tests for READING_LIST_TOOL_CONFIG."""

    def test_config_domain(self) -> None:
        """Test config has correct domain settings."""
        self.assertEqual(READING_LIST_TOOL_CONFIG.domain, "reading_item")
        self.assertEqual(READING_LIST_TOOL_CONFIG.domain_plural, "reading_list")
        self.assertEqual(READING_LIST_TOOL_CONFIG.endpoint_prefix, "/notion/reading-list")
        self.assertEqual(READING_LIST_TOOL_CONFIG.id_field, "item_id")

    def test_config_enum_fields(self) -> None:
        """Test config has correct enum fields."""
        self.assertIn("item_type", READING_LIST_TOOL_CONFIG.enum_fields)
        self.assertIn("status", READING_LIST_TOOL_CONFIG.enum_fields)
        self.assertIn("category", READING_LIST_TOOL_CONFIG.enum_fields)
        self.assertIn("priority", READING_LIST_TOOL_CONFIG.enum_fields)


class TestReadingQueryRequest(unittest.TestCase):
    """Tests for ReadingQueryRequest model (from API)."""

    def test_default_values(self) -> None:
        """Test default argument values."""
        args = ReadingQueryRequest()

        self.assertIsNone(args.status)
        self.assertIsNone(args.category)
        self.assertIsNone(args.priority)
        self.assertEqual(args.limit, 50)

    def test_all_filters(self) -> None:
        """Test setting all filter options."""
        args = ReadingQueryRequest(
            status=ReadingStatus.TO_READ,
            category=ReadingCategory.AI,
            priority=Priority.HIGH,
            limit=5,
        )

        self.assertEqual(args.status, ReadingStatus.TO_READ)
        self.assertEqual(args.category, ReadingCategory.AI)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.limit, 5)


class TestReadingItemCreateRequest(unittest.TestCase):
    """Tests for ReadingItemCreateRequest model (from API)."""

    def test_minimal_args(self) -> None:
        """Test creating with only required fields."""
        args = ReadingItemCreateRequest(title="Test Article", item_type=ReadingType.ARTICLE)

        self.assertEqual(args.title, "Test Article")
        self.assertEqual(args.item_type, ReadingType.ARTICLE)
        self.assertEqual(args.status, ReadingStatus.TO_READ)
        self.assertIsNone(args.priority)
        self.assertIsNone(args.category)
        self.assertIsNone(args.item_url)

    def test_full_args(self) -> None:
        """Test creating with all fields."""
        args = ReadingItemCreateRequest(
            title="AI Paper",
            item_type=ReadingType.ARTICLE,
            status=ReadingStatus.READING_NOW,
            priority=Priority.HIGH,
            category=ReadingCategory.AI,
            item_url="https://example.com/paper",
        )

        self.assertEqual(args.title, "AI Paper")
        self.assertEqual(args.item_type, ReadingType.ARTICLE)
        self.assertEqual(args.status, ReadingStatus.READING_NOW)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.category, ReadingCategory.AI)
        self.assertEqual(args.item_url, "https://example.com/paper")


class TestReadingListToolHandlers(unittest.TestCase):
    """Tests for reading list tool handlers."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tools = get_reading_list_tools()
        self.tool_dict = {t.name: t for t in self.tools}

    @patch("src.agent.tools.factory._get_client")
    def test_query_handler(self, mock_get_client: MagicMock) -> None:
        """Test query_reading_list handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "item-1"}]}

        tool = self.tool_dict["query_reading_list"]
        args = ReadingQueryRequest(status=ReadingStatus.TO_READ)
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/reading-list/query")
        self.assertEqual(result["count"], 1)

    @patch("src.agent.tools.factory._get_client")
    def test_get_handler(self, mock_get_client: MagicMock) -> None:
        """Test get_reading_item handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "page-123", "title": "Test Article"}

        tool = self.tool_dict["get_reading_item"]
        args = tool.args_model(item_id="page-123")
        result = tool.handler(args)

        mock_client.get.assert_called_once_with("/notion/reading-list/page-123")
        self.assertEqual(result["item"]["id"], "page-123")

    @patch("src.agent.tools.factory._get_client")
    def test_create_handler(self, mock_get_client: MagicMock) -> None:
        """Test create_reading_item handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "created": [{"id": "new-page", "title": "New Article"}],
            "failed": [],
        }

        tool = self.tool_dict["create_reading_list"]
        item = AgentReadingItemCreateArgs(
            title="New Article", item_type=ReadingType.ARTICLE, category=ReadingCategory.AI
        )
        args = tool.args_model(items=[item])
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/reading-list")
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 0)

    @patch("src.agent.tools.factory._get_client")
    def test_update_handler(self, mock_get_client: MagicMock) -> None:
        """Test update_reading_item handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "page-123", "title": "Updated"}

        tool = self.tool_dict["update_reading_item"]
        args = tool.args_model(item_id="page-123", title="Updated")
        result = tool.handler(args)

        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/reading-list/page-123")
        # item_id should not be in payload
        payload = call_args[1]["json"]
        self.assertNotIn("item_id", payload)
        self.assertTrue(result["updated"])

    def test_update_no_properties_error(self) -> None:
        """Test update with no properties returns error."""
        tool = self.tool_dict["update_reading_item"]
        args = tool.args_model(item_id="page-123")
        result = tool.handler(args)

        self.assertFalse(result["updated"])
        self.assertIn("error", result)

    @patch("src.agent.tools.factory._get_client")
    def test_update_with_item_type(self, mock_get_client: MagicMock) -> None:
        """Test updating with item type."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "page-123"}

        tool = self.tool_dict["update_reading_item"]
        args = tool.args_model(item_id="page-123", item_type=ReadingType.BOOK)
        result = tool.handler(args)

        call_args = mock_client.patch.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["item_type"], "Book")
        self.assertTrue(result["updated"])


if __name__ == "__main__":
    unittest.main()
