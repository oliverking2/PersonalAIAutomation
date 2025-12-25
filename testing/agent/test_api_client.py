"""Tests for AgentAPIClient."""

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import ConnectionError as RequestsConnectionError

from src.agent.api_client import AgentAPIClient, AgentAPIClientError


class TestAgentAPIClient(unittest.TestCase):
    """Tests for AgentAPIClient."""

    def test_init_with_defaults(self) -> None:
        """Test client initialisation with environment variables."""
        with patch.dict(
            "os.environ",
            {"API_AUTH_TOKEN": "test-token"},
            clear=False,
        ):
            client = AgentAPIClient()

            self.assertEqual(client.base_url, "http://localhost:8000")
            self.assertEqual(client.api_token, "test-token")
            client.close()

    def test_init_with_custom_values(self) -> None:
        """Test client initialisation with custom values."""
        client = AgentAPIClient(
            base_url="http://example.com",
            api_token="custom-token",
            timeout=60,
        )

        self.assertEqual(client.base_url, "http://example.com")
        self.assertEqual(client.api_token, "custom-token")
        self.assertEqual(client.timeout, 60)
        client.close()

    def test_init_without_token_raises_error(self) -> None:
        """Test that missing API token raises ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                AgentAPIClient()

            self.assertIn("API_AUTH_TOKEN", str(ctx.exception))

    @patch("src.agent.api_client.requests.Session")
    def test_get_request(self, mock_session_class: MagicMock) -> None:
        """Test GET request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_session.request.return_value = mock_response

        client = AgentAPIClient(api_token="test-token")
        result = client.get("/test", params={"key": "value"})

        self.assertEqual(result, {"data": "value"})
        mock_session.request.assert_called_once_with(
            "GET",
            "http://localhost:8000/test",
            params={"key": "value"},
            json=None,
            timeout=30,
        )

    @patch("src.agent.api_client.requests.Session")
    def test_post_request(self, mock_session_class: MagicMock) -> None:
        """Test POST request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"created": True}
        mock_session.request.return_value = mock_response

        client = AgentAPIClient(api_token="test-token")
        result = client.post("/test", json={"title": "Test"})

        self.assertEqual(result, {"created": True})
        mock_session.request.assert_called_once_with(
            "POST",
            "http://localhost:8000/test",
            params=None,
            json={"title": "Test"},
            timeout=30,
        )

    @patch("src.agent.api_client.requests.Session")
    def test_patch_request(self, mock_session_class: MagicMock) -> None:
        """Test PATCH request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"updated": True}
        mock_session.request.return_value = mock_response

        client = AgentAPIClient(api_token="test-token")
        result = client.patch("/test/123", json={"title": "Updated"})

        self.assertEqual(result, {"updated": True})
        mock_session.request.assert_called_once_with(
            "PATCH",
            "http://localhost:8000/test/123",
            params=None,
            json={"title": "Updated"},
            timeout=30,
        )

    @patch("src.agent.api_client.requests.Session")
    def test_request_handles_http_error(self, mock_session_class: MagicMock) -> None:
        """Test that HTTP errors are converted to AgentAPIClientError."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not found"}
        mock_session.request.return_value = mock_response

        client = AgentAPIClient(api_token="test-token")

        with self.assertRaises(AgentAPIClientError) as ctx:
            client.get("/not-found")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Not found", str(ctx.exception))

    @patch("src.agent.api_client.requests.Session")
    def test_request_handles_connection_error(self, mock_session_class: MagicMock) -> None:
        """Test that connection errors are converted to AgentAPIClientError."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = RequestsConnectionError("Connection refused")

        client = AgentAPIClient(api_token="test-token")

        with self.assertRaises(AgentAPIClientError) as ctx:
            client.get("/test")

        self.assertIn("Request failed", str(ctx.exception))

    @patch("src.agent.api_client.requests.Session")
    def test_context_manager(self, mock_session_class: MagicMock) -> None:
        """Test context manager usage."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_session.request.return_value = mock_response

        with AgentAPIClient(api_token="test-token") as client:
            result = client.get("/test")

        self.assertEqual(result, {"data": "value"})
        mock_session.close.assert_called_once()

    @patch("src.agent.api_client.requests.Session")
    def test_extract_error_detail_with_detail_key(self, mock_session_class: MagicMock) -> None:
        """Test error detail extraction with detail key."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Validation error"}
        mock_session.request.return_value = mock_response

        client = AgentAPIClient(api_token="test-token")

        with self.assertRaises(AgentAPIClientError) as ctx:
            client.post("/test")

        self.assertIn("Validation error", str(ctx.exception))

    @patch("src.agent.api_client.requests.Session")
    def test_extract_error_detail_with_text_fallback(self, mock_session_class: MagicMock) -> None:
        """Test error detail extraction falls back to text."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Internal Server Error"
        mock_session.request.return_value = mock_response

        client = AgentAPIClient(api_token="test-token")

        with self.assertRaises(AgentAPIClientError) as ctx:
            client.get("/test")

        self.assertIn("Internal Server Error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
