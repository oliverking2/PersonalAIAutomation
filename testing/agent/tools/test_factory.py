"""Tests for CRUD tool factory."""

import unittest
from enum import StrEnum
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.agent.enums import RiskLevel
from src.agent.tools.factory import (
    CRUDToolConfig,
    _create_create_tool,
    _create_get_tool,
    _create_query_tool,
    _create_update_tool,
    _format_enum_hints,
    create_crud_tools,
)


class MockStatus(StrEnum):
    """Mock status enum for testing."""

    PENDING = "Pending"
    ACTIVE = "Active"
    DONE = "Done"


class MockPriority(StrEnum):
    """Mock priority enum for testing."""

    LOW = "Low"
    HIGH = "High"


class MockQueryRequest(BaseModel):
    """Mock query request for testing."""

    status: MockStatus | None = None
    limit: int = 10


class MockCreateRequest(BaseModel):
    """Mock create request for testing."""

    name: str
    status: MockStatus = MockStatus.PENDING


class MockUpdateRequest(BaseModel):
    """Mock update request for testing."""

    name: str | None = None
    status: MockStatus | None = None


class TestFormatEnumHints(unittest.TestCase):
    """Tests for _format_enum_hints function."""

    def test_empty_enum_fields(self) -> None:
        """Test with empty enum fields."""
        result = _format_enum_hints({})
        self.assertEqual(result, "")

    def test_single_enum_field(self) -> None:
        """Test with a single enum field."""
        result = _format_enum_hints({"status": MockStatus})

        self.assertIn("status", result)
        self.assertIn("Pending", result)
        self.assertIn("Active", result)
        self.assertIn("Done", result)

    def test_multiple_enum_fields(self) -> None:
        """Test with multiple enum fields."""
        result = _format_enum_hints(
            {
                "status": MockStatus,
                "priority": MockPriority,
            }
        )

        self.assertIn("status", result)
        self.assertIn("priority", result)
        self.assertIn("Pending", result)
        self.assertIn("Low", result)
        self.assertIn("High", result)


class TestCRUDToolConfig(unittest.TestCase):
    """Tests for CRUDToolConfig dataclass."""

    def test_config_creation(self) -> None:
        """Test creating a config with all required fields."""
        config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Query widgets.",
            get_description="Get a widget.",
            create_description="Create widgets.",
            update_description="Update a widget.",
        )

        self.assertEqual(config.domain, "widget")
        self.assertEqual(config.domain_plural, "widgets")
        self.assertEqual(config.endpoint_prefix, "/api/widgets")
        self.assertEqual(config.id_field, "widget_id")
        self.assertEqual(config.name_field, "name")
        self.assertEqual(config.enum_fields, {})
        self.assertEqual(config.tags, frozenset())

    def test_config_with_optional_fields(self) -> None:
        """Test creating a config with optional fields."""
        config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Custom query description",
            get_description="Get a widget.",
            create_description="Create widgets.",
            update_description="Update a widget.",
            enum_fields={"status": MockStatus},
            tags=frozenset({"widgets", "test"}),
        )

        self.assertEqual(config.enum_fields, {"status": MockStatus})
        self.assertEqual(config.tags, frozenset({"widgets", "test"}))
        self.assertEqual(config.query_description, "Custom query description")


class TestCreateCrudTools(unittest.TestCase):
    """Tests for create_crud_tools function."""

    def setUp(self) -> None:
        """Set up test config."""
        self.config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Query widgets.",
            get_description="Get a widget.",
            create_description="Create widgets.",
            update_description="Update a widget.",
            enum_fields={"status": MockStatus},
            tags=frozenset({"widgets"}),
        )

    def test_creates_four_tools(self) -> None:
        """Test that factory creates exactly four tools."""
        tools = create_crud_tools(self.config)

        self.assertEqual(len(tools), 4)

    def test_tool_names(self) -> None:
        """Test that tools have correct names."""
        tools = create_crud_tools(self.config)
        names = {t.name for t in tools}

        self.assertEqual(
            names,
            {
                "query_widgets",
                "get_widget",
                "create_widgets",
                "update_widget",
            },
        )

    def test_tool_risk_levels(self) -> None:
        """Test that tools have correct risk levels."""
        tools = create_crud_tools(self.config)
        tool_dict = {t.name: t for t in tools}

        self.assertEqual(tool_dict["query_widgets"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["get_widget"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["create_widgets"].risk_level, RiskLevel.SAFE)
        self.assertEqual(tool_dict["update_widget"].risk_level, RiskLevel.SENSITIVE)

    def test_tool_tags(self) -> None:
        """Test that tools have correct tags."""
        tools = create_crud_tools(self.config)
        tool_dict = {t.name: t for t in tools}

        # All should have base tags plus operation-specific tags
        self.assertIn("widgets", tool_dict["query_widgets"].tags)
        self.assertIn("query", tool_dict["query_widgets"].tags)
        self.assertIn("list", tool_dict["query_widgets"].tags)

        self.assertIn("widgets", tool_dict["get_widget"].tags)
        self.assertIn("get", tool_dict["get_widget"].tags)

        self.assertIn("widgets", tool_dict["create_widgets"].tags)
        self.assertIn("create", tool_dict["create_widgets"].tags)

        self.assertIn("widgets", tool_dict["update_widget"].tags)
        self.assertIn("update", tool_dict["update_widget"].tags)


class TestQueryToolGeneration(unittest.TestCase):
    """Tests for query tool generation."""

    def setUp(self) -> None:
        """Set up test config."""
        self.config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Query widgets with fuzzy search.",
            get_description="Get a widget by ID.",
            create_description="Create widgets.",
            update_description="Update a widget.",
            enum_fields={"status": MockStatus},
        )

    def test_query_tool_uses_provided_description(self) -> None:
        """Test query tool uses the provided description."""
        tool = _create_query_tool(self.config)

        self.assertEqual(tool.description, "Query widgets with fuzzy search.")

    @patch("src.agent.tools.factory._get_client")
    def test_query_tool_handler(self, mock_get_client: MagicMock) -> None:
        """Test query tool handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {"results": [{"id": "1"}]}

        tool = _create_query_tool(self.config)
        args = MockQueryRequest(status=MockStatus.ACTIVE)
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/api/widgets/query")
        self.assertEqual(result, {"items": [{"id": "1"}], "count": 1})


class TestGetToolGeneration(unittest.TestCase):
    """Tests for get tool generation."""

    def setUp(self) -> None:
        """Set up test config."""
        self.config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Query widgets.",
            get_description="Get a widget by ID.",
            create_description="Create widgets.",
            update_description="Update a widget.",
        )

    def test_get_tool_uses_provided_description(self) -> None:
        """Test get tool uses the provided description."""
        tool = _create_get_tool(self.config)

        self.assertEqual(tool.description, "Get a widget by ID.")

    @patch("src.agent.tools.factory._get_client")
    def test_get_tool_handler(self, mock_get_client: MagicMock) -> None:
        """Test get tool handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = {"id": "widget-123", "name": "Test"}

        tool = _create_get_tool(self.config)
        # Create args using the dynamically generated model
        args = tool.args_model(widget_id="widget-123")
        result = tool.handler(args)

        mock_client.get.assert_called_once_with("/api/widgets/widget-123")
        self.assertEqual(result, {"item": {"id": "widget-123", "name": "Test"}})


class TestCreateToolGeneration(unittest.TestCase):
    """Tests for create tool generation."""

    def setUp(self) -> None:
        """Set up test config."""
        self.config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Query widgets.",
            get_description="Get a widget.",
            create_description="Create widgets.",
            update_description="Update a widget.",
            enum_fields={"status": MockStatus},
        )

    def test_create_tool_uses_provided_description(self) -> None:
        """Test create tool uses the provided description."""
        tool = _create_create_tool(self.config)

        self.assertEqual(tool.description, "Create widgets.")

    @patch("src.agent.tools.factory._get_client")
    def test_create_tool_handler(self, mock_get_client: MagicMock) -> None:
        """Test create tool handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "created": [{"id": "new-widget", "name": "New Widget"}],
            "failed": [],
        }

        tool = _create_create_tool(self.config)
        # Create args using the bulk args model with items list
        item = MockCreateRequest(name="New Widget")
        args = tool.args_model(items=[item])
        result = tool.handler(args)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        self.assertEqual(call_args[0][0], "/api/widgets")
        # Response includes items list and counts
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["id"], "new-widget")
        self.assertEqual(result["items"][0]["name"], "New Widget")
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 0)

    @patch("src.agent.tools.factory._get_client")
    def test_create_tool_handler_bulk(self, mock_get_client: MagicMock) -> None:
        """Test create tool handler supports bulk creation."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = {
            "created": [
                {"id": "widget-1", "name": "Widget 1"},
                {"id": "widget-2", "name": "Widget 2"},
            ],
            "failed": [],
        }

        tool = _create_create_tool(self.config)
        # Create multiple items in one call
        items = [
            MockCreateRequest(name="Widget 1"),
            MockCreateRequest(name="Widget 2"),
        ]
        args = tool.args_model(items=items)
        result = tool.handler(args)

        # All items are sent in a single request
        self.assertEqual(mock_client.post.call_count, 1)
        # Response includes all created items
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["failed"], 0)

    @patch("src.agent.tools.factory._get_client")
    def test_create_tool_handler_partial_failure(self, mock_get_client: MagicMock) -> None:
        """Test create tool handler handles partial failures from API."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        # API returns partial success response
        mock_client.post.return_value = {
            "created": [{"id": "widget-1", "name": "Widget 1"}],
            "failed": [{"name": "Widget 2", "error": "Validation error: duplicate name"}],
        }

        tool = _create_create_tool(self.config)
        items = [
            MockCreateRequest(name="Widget 1"),
            MockCreateRequest(name="Widget 2"),
        ]
        args = tool.args_model(items=items)
        result = tool.handler(args)

        # Should have partial success
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"], "Widget 1")
        # Should have failure details
        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["name"], "Widget 2")
        self.assertIn("Validation error", result["failures"][0]["error"])


class TestUpdateToolGeneration(unittest.TestCase):
    """Tests for update tool generation."""

    def setUp(self) -> None:
        """Set up test config."""
        self.config = CRUDToolConfig(
            domain="widget",
            domain_plural="widgets",
            endpoint_prefix="/api/widgets",
            id_field="widget_id",
            name_field="name",
            query_model=MockQueryRequest,
            create_model=MockCreateRequest,
            update_model=MockUpdateRequest,
            query_description="Query widgets.",
            get_description="Get a widget.",
            create_description="Create widgets.",
            update_description="Update a widget.",
        )

    def test_update_tool_is_sensitive(self) -> None:
        """Test update tool is marked as sensitive."""
        tool = _create_update_tool(self.config)

        self.assertEqual(tool.risk_level, RiskLevel.SENSITIVE)

    @patch("src.agent.tools.factory._get_client")
    def test_update_tool_handler(self, mock_get_client: MagicMock) -> None:
        """Test update tool handler makes correct API call."""
        mock_client = MagicMock()
        mock_get_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_get_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = {"id": "widget-123", "name": "Updated"}

        tool = _create_update_tool(self.config)
        # Create args using the dynamically generated model
        args = tool.args_model(widget_id="widget-123", name="Updated")
        result = tool.handler(args)

        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        self.assertEqual(call_args[0][0], "/api/widgets/widget-123")
        # ID should not be in payload
        payload = call_args[1]["json"]
        self.assertNotIn("widget_id", payload)
        self.assertEqual(payload["name"], "Updated")
        self.assertEqual(result, {"item": {"id": "widget-123", "name": "Updated"}, "updated": True})

    @patch("src.agent.tools.factory._get_client")
    def test_update_tool_no_properties_error(self, mock_get_client: MagicMock) -> None:
        """Test update tool returns error when no properties provided."""
        tool = _create_update_tool(self.config)
        # Create args with only ID
        args = tool.args_model(widget_id="widget-123")
        result = tool.handler(args)

        self.assertFalse(result["updated"])
        self.assertIn("error", result)
        mock_get_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
