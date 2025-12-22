"""Tests for Notion client module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from src.notion.client import REQUEST_TIMEOUT, NotionClient
from src.notion.exceptions import NotionClientError


class TestNotionClientInitialisation(unittest.TestCase):
    """Tests for NotionClient initialisation."""

    @patch.dict("os.environ", {"NOTION_INTEGRATION_SECRET": "test-token"})
    def test_initialisation_with_env_var(self) -> None:
        """Test successful initialisation with environment variable."""
        client = NotionClient()

        self.assertEqual(client._token, "test-token")

    def test_initialisation_with_explicit_parameter(self) -> None:
        """Test successful initialisation with explicit parameter."""
        client = NotionClient(token="explicit-token")

        self.assertEqual(client._token, "explicit-token")

    @patch.dict("os.environ", {}, clear=True)
    def test_initialisation_missing_token_raises_value_error(self) -> None:
        """Test initialisation fails when token is missing."""
        with self.assertRaises(ValueError) as context:
            NotionClient()

        self.assertIn("token", str(context.exception).lower())

    @patch.dict("os.environ", {"NOTION_INTEGRATION_SECRET": "env-token"})
    def test_explicit_parameter_overrides_env_var(self) -> None:
        """Test that explicit parameter takes precedence over environment variable."""
        client = NotionClient(token="explicit-token")

        self.assertEqual(client._token, "explicit-token")


class TestNotionClientHeaders(unittest.TestCase):
    """Tests for NotionClient headers property."""

    def test_headers_contains_required_fields(self) -> None:
        """Test that headers contain all required Notion API fields."""
        client = NotionClient(token="test-token")
        headers = client._headers

        self.assertIn("Authorization", headers)
        self.assertIn("Content-Type", headers)
        self.assertIn("Notion-Version", headers)
        self.assertEqual(headers["Authorization"], "Bearer test-token")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Notion-Version"], "2025-09-03")


class TestNotionClientGetDatabase(unittest.TestCase):
    """Tests for NotionClient.get_database method."""

    @patch("src.notion.client.requests.get")
    def test_get_database_success(self, mock_get: MagicMock) -> None:
        """Test successful database retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "db-123",
            "title": [{"plain_text": "Tasks"}],
            "properties": {"Name": {"type": "title"}},
        }
        mock_get.return_value = mock_response

        client = NotionClient(token="test-token")
        result = client.get_database("db-123")

        self.assertEqual(result["id"], "db-123")
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        self.assertEqual(call_kwargs["timeout"], REQUEST_TIMEOUT)

    @patch("src.notion.client.requests.get")
    def test_get_database_timeout_raises_exception(self, mock_get: MagicMock) -> None:
        """Test that timeout raises NotionClientError."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        client = NotionClient(token="test-token")

        with self.assertRaises(NotionClientError) as context:
            client.get_database("db-123")

        self.assertIn("timed out", str(context.exception).lower())


class TestNotionClientQueryDataSource(unittest.TestCase):
    """Tests for NotionClient.query_data_source method."""

    @patch("src.notion.client.requests.post")
    def test_query_data_source_success(self, mock_post: MagicMock) -> None:
        """Test successful data source query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": "page-1"}],
            "has_more": False,
            "next_cursor": None,
        }
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")
        result = client.query_data_source("ds-123")

        self.assertEqual(len(result["results"]), 1)
        mock_post.assert_called_once()

    @patch("src.notion.client.requests.post")
    def test_query_data_source_with_filter(self, mock_post: MagicMock) -> None:
        """Test data source query with filter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "has_more": False}
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")
        filter_obj = {"property": "Status", "status": {"equals": "Done"}}
        client.query_data_source("ds-123", filter_=filter_obj)

        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["filter"], filter_obj)

    @patch("src.notion.client.requests.post")
    def test_query_data_source_http_error_raises_exception(self, mock_post: MagicMock) -> None:
        """Test that HTTP error raises NotionClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Data source not found"}
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")

        with self.assertRaises(NotionClientError) as context:
            client.query_data_source("invalid-ds")

        self.assertIn("404", str(context.exception))


class TestNotionClientQueryAllDataSource(unittest.TestCase):
    """Tests for NotionClient.query_all_data_source method."""

    @patch("src.notion.client.requests.post")
    def test_query_all_single_page(self, mock_post: MagicMock) -> None:
        """Test query_all with single page of results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": "page-1"}, {"id": "page-2"}],
            "has_more": False,
            "next_cursor": None,
        }
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")
        result = client.query_all_data_source("ds-123")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "page-1")
        mock_post.assert_called_once()

    @patch("src.notion.client.requests.post")
    def test_query_all_multiple_pages(self, mock_post: MagicMock) -> None:
        """Test query_all with multiple pages of results."""
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "results": [{"id": "page-1"}],
            "has_more": True,
            "next_cursor": "cursor-1",
        }

        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "results": [{"id": "page-2"}],
            "has_more": True,
            "next_cursor": "cursor-2",
        }

        mock_response_3 = MagicMock()
        mock_response_3.status_code = 200
        mock_response_3.json.return_value = {
            "results": [{"id": "page-3"}],
            "has_more": False,
            "next_cursor": None,
        }

        mock_post.side_effect = [mock_response_1, mock_response_2, mock_response_3]

        client = NotionClient(token="test-token")
        result = client.query_all_data_source("ds-123")

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["id"], "page-1")
        self.assertEqual(result[1]["id"], "page-2")
        self.assertEqual(result[2]["id"], "page-3")
        self.assertEqual(mock_post.call_count, 3)

    @patch("src.notion.client.requests.post")
    def test_query_all_empty_results(self, mock_post: MagicMock) -> None:
        """Test query_all with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [],
            "has_more": False,
            "next_cursor": None,
        }
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")
        result = client.query_all_data_source("ds-123")

        self.assertEqual(len(result), 0)

    @patch("src.notion.client.requests.post")
    def test_query_all_with_filter(self, mock_post: MagicMock) -> None:
        """Test query_all passes filter to underlying query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": "page-1"}],
            "has_more": False,
            "next_cursor": None,
        }
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")
        filter_obj = {"property": "Status", "status": {"equals": "Done"}}
        client.query_all_data_source("ds-123", filter_=filter_obj)

        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["filter"], filter_obj)


class TestNotionClientCreatePage(unittest.TestCase):
    """Tests for NotionClient.create_page method."""

    @patch("src.notion.client.requests.post")
    def test_create_page_success(self, mock_post: MagicMock) -> None:
        """Test successful page creation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "page-new",
            "properties": {"Task name": {"title": [{"plain_text": "New Task"}]}},
            "url": "https://notion.so/New-Task",
        }
        mock_post.return_value = mock_response

        client = NotionClient(token="test-token")
        properties = {"Task name": {"title": [{"text": {"content": "New Task"}}]}}
        result = client.create_page("ds-123", properties)

        self.assertEqual(result["id"], "page-new")
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["parent"]["data_source_id"], "ds-123")


class TestNotionClientUpdatePage(unittest.TestCase):
    """Tests for NotionClient.update_page method."""

    @patch("src.notion.client.requests.patch")
    def test_update_page_success(self, mock_patch: MagicMock) -> None:
        """Test successful page update."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "page-123",
            "properties": {"Status": {"status": {"name": "Done"}}},
            "url": "https://notion.so/Task",
        }
        mock_patch.return_value = mock_response

        client = NotionClient(token="test-token")
        properties = {"Status": {"status": {"name": "Done"}}}
        result = client.update_page("page-123", properties)

        self.assertEqual(result["id"], "page-123")
        mock_patch.assert_called_once()


class TestNotionClientGetPage(unittest.TestCase):
    """Tests for NotionClient.get_page method."""

    @patch("src.notion.client.requests.get")
    def test_get_page_success(self, mock_get: MagicMock) -> None:
        """Test successful page retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "page-123",
            "properties": {"Task name": {"title": [{"plain_text": "My Task"}]}},
            "url": "https://notion.so/My-Task",
        }
        mock_get.return_value = mock_response

        client = NotionClient(token="test-token")
        result = client.get_page("page-123")

        self.assertEqual(result["id"], "page-123")


class TestNotionClientListTemplates(unittest.TestCase):
    """Tests for NotionClient.list_data_source_templates method."""

    @patch("src.notion.client.requests.get")
    def test_list_templates_success(self, mock_get: MagicMock) -> None:
        """Test successful template listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": "template-1", "name": "Tasks"}]}
        mock_get.return_value = mock_response

        client = NotionClient(token="test-token")
        result = client.list_data_source_templates()

        self.assertEqual(len(result["results"]), 1)


if __name__ == "__main__":
    unittest.main()
