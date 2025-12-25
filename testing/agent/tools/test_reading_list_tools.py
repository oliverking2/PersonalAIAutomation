"""Tests for reading list tool handlers."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from src.agent.enums import RiskLevel
from src.agent.tools.reading_list import (
    GetReadingItemArgs,
    UpdateReadingItemArgs,
    create_reading_item,
    get_reading_item,
    get_reading_list_tools,
    query_reading_list,
    update_reading_item,
)
from src.api.notion.reading_list.models import (
    ReadingItemCreateRequest,
    ReadingQueryRequest,
)
from src.notion.enums import Priority, ReadingCategory, ReadingStatus


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
                "create_reading_item",
                "update_reading_item",
            },
        )

    def test_query_and_get_are_safe(self) -> None:
        """Test that query and get tools are marked as safe."""
        tools = get_reading_list_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_reading_list"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_reading_item"].risk_level, RiskLevel.SAFE)

    def test_create_and_update_are_sensitive(self) -> None:
        """Test that create and update tools are marked as sensitive."""
        tools = get_reading_list_tools()
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["create_reading_item"].risk_level, RiskLevel.SENSITIVE)
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
        args = ReadingItemCreateRequest(title="Test Article")

        self.assertEqual(args.title, "Test Article")
        self.assertEqual(args.status, ReadingStatus.TO_READ)
        self.assertIsNone(args.priority)
        self.assertIsNone(args.category)
        self.assertIsNone(args.item_url)

    def test_full_args(self) -> None:
        """Test creating with all fields."""
        args = ReadingItemCreateRequest(
            title="AI Paper",
            status=ReadingStatus.READING_NOW,
            priority=Priority.HIGH,
            category=ReadingCategory.AI,
            item_url="https://example.com/paper",
        )

        self.assertEqual(args.title, "AI Paper")
        self.assertEqual(args.status, ReadingStatus.READING_NOW)
        self.assertEqual(args.priority, Priority.HIGH)
        self.assertEqual(args.category, ReadingCategory.AI)
        self.assertEqual(args.item_url, "https://example.com/paper")


class TestUpdateReadingItemArgs(unittest.TestCase):
    """Tests for UpdateReadingItemArgs model."""

    def test_minimal_args(self) -> None:
        """Test creating with only item_id."""
        args = UpdateReadingItemArgs(item_id="page-123")

        self.assertEqual(args.item_id, "page-123")
        self.assertIsNone(args.title)
        self.assertIsNone(args.status)

    def test_with_read_date(self) -> None:
        """Test update with read_date."""
        args = UpdateReadingItemArgs(
            item_id="page-123",
            status=ReadingStatus.COMPLETED,
            read_date=date(2024, 1, 15),
        )

        self.assertEqual(args.status, ReadingStatus.COMPLETED)
        self.assertEqual(args.read_date, date(2024, 1, 15))


class TestQueryReadingListHandler(unittest.TestCase):
    """Tests for query_reading_list handler."""

    @patch("src.agent.tools.reading_list._get_client")
    def test_query_without_filters(self, mock_get_client: MagicMock) -> None:
        """Test querying without any filters."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "item-1", "title": "Test"}]}

        result = query_reading_list(ReadingQueryRequest())

        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["items"]), 1)
        mock_client.post.assert_called_once_with("/notion/reading-list/query", json={"limit": 50})

    @patch("src.agent.tools.reading_list._get_client")
    def test_query_with_status_filter(self, mock_get_client: MagicMock) -> None:
        """Test querying with status filter."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        query_reading_list(ReadingQueryRequest(status=ReadingStatus.TO_READ))

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["status"], "To Read")

    @patch("src.agent.tools.reading_list._get_client")
    def test_query_with_all_filters(self, mock_get_client: MagicMock) -> None:
        """Test querying with all filters."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": []}

        query_reading_list(
            ReadingQueryRequest(
                status=ReadingStatus.READING_NOW,
                category=ReadingCategory.AI,
                priority=Priority.HIGH,
                limit=5,
            )
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["status"], "Reading Now")
        self.assertEqual(payload["category"], "AI")
        self.assertEqual(payload["priority"], "High")
        self.assertEqual(payload["limit"], 5)


class TestGetReadingItemHandler(unittest.TestCase):
    """Tests for get_reading_item handler."""

    @patch("src.agent.tools.reading_list._get_client")
    def test_get_item(self, mock_get_client: MagicMock) -> None:
        """Test getting a reading item."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "page-123", "title": "Test Article"}

        result = get_reading_item(GetReadingItemArgs(item_id="page-123"))

        self.assertEqual(result["item"]["id"], "page-123")
        self.assertEqual(result["item"]["title"], "Test Article")
        mock_client.get.assert_called_once_with("/notion/reading-list/page-123")


class TestCreateReadingItemHandler(unittest.TestCase):
    """Tests for create_reading_item handler."""

    @patch("src.agent.tools.reading_list._get_client")
    def test_create_item_minimal(self, mock_get_client: MagicMock) -> None:
        """Test creating a reading item with minimal fields."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-page", "title": "New Article"}

        result = create_reading_item(ReadingItemCreateRequest(title="New Article"))

        self.assertTrue(result["created"])
        self.assertEqual(result["item"]["title"], "New Article")
        mock_client.post.assert_called_once()

        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/notion/reading-list")
        payload = call_args[1]["json"]
        self.assertEqual(payload["title"], "New Article")
        self.assertEqual(payload["status"], "To Read")

    @patch("src.agent.tools.reading_list._get_client")
    def test_create_item_full(self, mock_get_client: MagicMock) -> None:
        """Test creating a reading item with all fields."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"id": "new-page", "title": "AI Paper"}

        result = create_reading_item(
            ReadingItemCreateRequest(
                title="AI Paper",
                status=ReadingStatus.READING_NOW,
                priority=Priority.HIGH,
                category=ReadingCategory.AI,
                item_url="https://example.com/paper",
            )
        )

        self.assertTrue(result["created"])
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["title"], "AI Paper")
        self.assertEqual(payload["status"], "Reading Now")
        self.assertEqual(payload["priority"], "High")
        self.assertEqual(payload["category"], "AI")
        self.assertEqual(payload["item_url"], "https://example.com/paper")


class TestUpdateReadingItemHandler(unittest.TestCase):
    """Tests for update_reading_item handler."""

    @patch("src.agent.tools.reading_list._get_client")
    def test_update_item(self, mock_get_client: MagicMock) -> None:
        """Test updating a reading item."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "page-123", "title": "Updated Title"}

        result = update_reading_item(
            UpdateReadingItemArgs(
                item_id="page-123",
                title="Updated Title",
                status=ReadingStatus.COMPLETED,
            )
        )

        self.assertTrue(result["updated"])
        self.assertEqual(result["item"]["title"], "Updated Title")
        mock_client.patch.assert_called_once()

        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/notion/reading-list/page-123")
        payload = call_args[1]["json"]
        self.assertEqual(payload["title"], "Updated Title")
        self.assertEqual(payload["status"], "Completed")
        # item_id should not be in payload
        self.assertNotIn("item_id", payload)

    def test_update_no_properties(self) -> None:
        """Test update with no properties returns error."""
        result = update_reading_item(UpdateReadingItemArgs(item_id="page-123"))

        self.assertFalse(result["updated"])
        self.assertIn("error", result)

    @patch("src.agent.tools.reading_list._get_client")
    def test_update_with_read_date(self, mock_get_client: MagicMock) -> None:
        """Test updating with read date."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "page-123"}

        update_reading_item(
            UpdateReadingItemArgs(
                item_id="page-123",
                read_date=date(2024, 1, 15),
            )
        )

        call_args = mock_client.patch.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["read_date"], "2024-01-15")


if __name__ == "__main__":
    unittest.main()
