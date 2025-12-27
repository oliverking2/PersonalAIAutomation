"""Tests for Notion ideas endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_IDEAS_DATA_SOURCE_ID", "test-ideas-data-source-id")

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from testing.api.notion.fixtures import (
    DEFAULT_IDEA_GROUP,
    DEFAULT_IDEA_STATUS,
    build_idea_create_payload,
    build_notion_idea_page,
)


class TestQueryIdeasEndpoint(unittest.TestCase):
    """Tests for POST /notion/ideas/query endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_ideas_success(self, mock_client_class: MagicMock) -> None:
        """Test successful ideas query."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            build_notion_idea_page(
                page_id="idea-1",
                url="https://notion.so/Idea-1",
                idea="Mobile app for habit tracking",
            )
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/ideas/query",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        item = data["results"][0]
        self.assertEqual(item["idea"], "Mobile app for habit tracking")
        self.assertEqual(item["status"], DEFAULT_IDEA_STATUS)
        self.assertEqual(item["idea_group"], DEFAULT_IDEA_GROUP)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_ideas_with_group_filter(self, mock_client_class: MagicMock) -> None:
        """Test ideas query with idea group filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/ideas/query",
            headers=self.auth_headers,
            json={"idea_group": DEFAULT_IDEA_GROUP},
        )

        self.assertEqual(response.status_code, 200)
        # Verify the combined filter was built correctly
        # (includes exclude Archived + idea_group filter)
        call_args = mock_client.query_all_data_source.call_args
        filter_arg = call_args[1]["filter_"]
        self.assertIn("and", filter_arg)
        self.assertEqual(len(filter_arg["and"]), 2)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_query_ideas_with_name_filter(self, mock_client_class: MagicMock) -> None:
        """Test ideas query with fuzzy name filter."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            build_notion_idea_page(
                page_id="idea-1",
                url="https://notion.so/App-Idea",
                idea="Mobile app for habit tracking",
            ),
            build_notion_idea_page(
                page_id="idea-2",
                url="https://notion.so/Web-Project",
                idea="Web dashboard for analytics",
            ),
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/ideas/query",
            headers=self.auth_headers,
            json={"name_filter": "mobile"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Fuzzy match should rank mobile app higher
        self.assertEqual(data["fuzzy_match_quality"], "good")


class TestGetIdeaEndpoint(unittest.TestCase):
    """Tests for GET /notion/ideas/{idea_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_get_idea_success(self, mock_client_class: MagicMock) -> None:
        """Test successful idea retrieval."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = build_notion_idea_page(
            page_id="idea-123",
            url="https://notion.so/My-Idea",
            idea="Build a CLI tool",
        )
        mock_client.get_page_content.return_value = []
        mock_client_class.return_value = mock_client

        response = self.client.get(
            "/notion/ideas/idea-123",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "idea-123")
        self.assertEqual(data["idea"], "Build a CLI tool")
        self.assertEqual(data["status"], DEFAULT_IDEA_STATUS)
        self.assertEqual(data["idea_group"], DEFAULT_IDEA_GROUP)


class TestCreateIdeaEndpoint(unittest.TestCase):
    """Tests for POST /notion/ideas endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_idea_success(self, mock_client_class: MagicMock) -> None:
        """Test successful idea creation with all fields."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []  # No duplicates
        mock_client.create_page.return_value = build_notion_idea_page(
            page_id="idea-new",
            url="https://notion.so/New-Idea",
            idea="New mobile app idea",
        )
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/ideas",
            headers=self.auth_headers,
            json=[
                build_idea_create_payload(
                    idea="New mobile app idea",
                    idea_group=DEFAULT_IDEA_GROUP,
                )
            ],
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data["created"]), 1)
        self.assertEqual(len(data["failed"]), 0)
        self.assertEqual(data["created"][0]["id"], "idea-new")
        self.assertEqual(data["created"][0]["idea"], "New mobile app idea")
        self.assertEqual(data["created"][0]["status"], DEFAULT_IDEA_STATUS)
        self.assertEqual(data["created"][0]["idea_group"], DEFAULT_IDEA_GROUP)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_idea_minimal(self, mock_client_class: MagicMock) -> None:
        """Test idea creation with minimal fields."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []  # No duplicates
        mock_client.create_page.return_value = {
            "id": "idea-min",
            "url": "https://notion.so/Minimal",
            "properties": {
                "Idea": {"title": [{"plain_text": "Minimal idea"}]},
                "Status": {"status": {"name": DEFAULT_IDEA_STATUS}},
                "Idea Group": {"select": None},
            },
        }
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/ideas",
            headers=self.auth_headers,
            json=[build_idea_create_payload(idea="Minimal idea")],
        )

        self.assertEqual(response.status_code, 201)

    def test_create_idea_missing_title_returns_422(self) -> None:
        """Test that missing idea title returns 422 with readable error."""
        response = self.client.post(
            "/notion/ideas",
            headers=self.auth_headers,
            json=[{"idea_group": DEFAULT_IDEA_GROUP}],
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("idea", detail)
        self.assertIn("field required", detail)

    def test_create_idea_invalid_group_returns_422(self) -> None:
        """Test that invalid idea_group enum value returns 422 with readable error."""
        response = self.client.post(
            "/notion/ideas",
            headers=self.auth_headers,
            json=[{"idea": "Test Idea", "idea_group": "Invalid"}],
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("idea_group", detail)
        self.assertIn("invalid value 'Invalid'", detail)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_create_idea_duplicate_returns_failure(self, mock_client_class: MagicMock) -> None:
        """Test that duplicate idea is reported in failures."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "existing-idea",
                "properties": {
                    "Idea": {"title": [{"plain_text": "Existing Idea"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.post(
            "/notion/ideas",
            headers=self.auth_headers,
            json=[build_idea_create_payload(idea="existing idea")],
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data["created"]), 0)
        self.assertEqual(len(data["failed"]), 1)
        self.assertEqual(data["failed"][0]["name"], "existing idea")
        self.assertIn("already exists", data["failed"][0]["error"])


class TestUpdateIdeaEndpoint(unittest.TestCase):
    """Tests for PATCH /notion/ideas/{idea_id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_idea_success(self, mock_client_class: MagicMock) -> None:
        """Test successful idea update."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = []  # No duplicate
        mock_client.update_page.return_value = build_notion_idea_page(
            page_id="idea-123",
            url="https://notion.so/Idea",
            idea="Updated Idea Title",
        )
        mock_client.get_page_content.return_value = []
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/ideas/idea-123",
            headers=self.auth_headers,
            json={"idea": "Updated Idea Title", "idea_group": DEFAULT_IDEA_GROUP},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["idea"], "Updated Idea Title")
        self.assertEqual(data["idea_group"], DEFAULT_IDEA_GROUP)

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_idea_no_fields_returns_400(self, mock_client_class: MagicMock) -> None:
        """Test that update with no fields returns 400."""
        mock_client_class.return_value = MagicMock()

        response = self.client.patch(
            "/notion/ideas/idea-123",
            headers=self.auth_headers,
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No properties or content to update", response.json()["detail"])

    @patch("src.api.notion.dependencies.NotionClient")
    def test_update_idea_duplicate_returns_409(self, mock_client_class: MagicMock) -> None:
        """Test that updating to duplicate idea returns 409 Conflict."""
        mock_client = MagicMock()
        mock_client.query_all_data_source.return_value = [
            {
                "id": "other-idea",
                "properties": {
                    "Idea": {"title": [{"plain_text": "Other Idea"}]},
                },
            }
        ]
        mock_client_class.return_value = mock_client

        response = self.client.patch(
            "/notion/ideas/idea-123",
            headers=self.auth_headers,
            json={"idea": "OTHER IDEA"},  # case insensitive match
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
