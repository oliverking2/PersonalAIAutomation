"""Tests for InternalAPIClient."""

import unittest
from unittest.mock import ANY, MagicMock, patch

from requests.exceptions import ConnectionError as RequestsConnectionError

from src.api.client import InternalAPIClient, InternalAPIClientError


class TestInternalAPIClient(unittest.TestCase):
    """Tests for InternalAPIClient."""

    def test_init_with_defaults(self) -> None:
        """Test client initialisation with environment variables."""
        with patch.dict(
            "os.environ",
            {"API_AUTH_TOKEN": "test-token"},
            clear=False,
        ):
            client = InternalAPIClient()

            self.assertEqual(client.base_url, "http://localhost:8000")
            self.assertEqual(client.api_token, "test-token")
            client.close()

    def test_init_with_api_host_and_port(self) -> None:
        """Test client initialisation with API_HOST and API_PORT."""
        with patch.dict(
            "os.environ",
            {
                "API_AUTH_TOKEN": "test-token",
                "API_HOST": "api",
                "API_PORT": "8080",
            },
            clear=False,
        ):
            client = InternalAPIClient()

            self.assertEqual(client.base_url, "http://api:8080")
            self.assertEqual(client.api_token, "test-token")
            client.close()

    def test_init_with_custom_values(self) -> None:
        """Test client initialisation with custom values."""
        client = InternalAPIClient(
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
                InternalAPIClient()

            self.assertIn("API_AUTH_TOKEN", str(ctx.exception))

    @patch("src.api.client.requests.Session")
    def test_get_request(self, mock_session_class: MagicMock) -> None:
        """Test GET request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_session.request.return_value = mock_response

        client = InternalAPIClient(api_token="test-token")
        result = client.get("/test", params={"key": "value"})

        self.assertEqual(result, {"data": "value"})
        mock_session.request.assert_called_once_with(
            "GET",
            "http://localhost:8000/test",
            params={"key": "value"},
            json=None,
            timeout=60,
            headers=ANY,
        )
        # Verify X-Request-ID header was sent
        call_headers = mock_session.request.call_args.kwargs["headers"]
        self.assertIn("X-Request-ID", call_headers)

    @patch("src.api.client.requests.Session")
    def test_post_request(self, mock_session_class: MagicMock) -> None:
        """Test POST request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"created": True}
        mock_session.request.return_value = mock_response

        client = InternalAPIClient(api_token="test-token")
        result = client.post("/test", json={"title": "Test"})

        self.assertEqual(result, {"created": True})
        mock_session.request.assert_called_once_with(
            "POST",
            "http://localhost:8000/test",
            params=None,
            json={"title": "Test"},
            timeout=60,
            headers=ANY,
        )

    @patch("src.api.client.requests.Session")
    def test_patch_request(self, mock_session_class: MagicMock) -> None:
        """Test PATCH request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"updated": True}
        mock_session.request.return_value = mock_response

        client = InternalAPIClient(api_token="test-token")
        result = client.patch("/test/123", json={"title": "Updated"})

        self.assertEqual(result, {"updated": True})
        mock_session.request.assert_called_once_with(
            "PATCH",
            "http://localhost:8000/test/123",
            params=None,
            json={"title": "Updated"},
            timeout=60,
            headers=ANY,
        )

    @patch("src.api.client.requests.Session")
    def test_request_handles_http_error(self, mock_session_class: MagicMock) -> None:
        """Test that HTTP errors are converted to InternalAPIClientError."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not found"}
        mock_session.request.return_value = mock_response

        client = InternalAPIClient(api_token="test-token")

        with self.assertRaises(InternalAPIClientError) as ctx:
            client.get("/not-found")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Not found", str(ctx.exception))

    @patch("src.api.client.requests.Session")
    def test_request_handles_connection_error(self, mock_session_class: MagicMock) -> None:
        """Test that connection errors are converted to InternalAPIClientError."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = RequestsConnectionError("Connection refused")

        client = InternalAPIClient(api_token="test-token")

        with self.assertRaises(InternalAPIClientError) as ctx:
            client.get("/test")

        self.assertIn("Request failed", str(ctx.exception))

    @patch("src.api.client.requests.Session")
    def test_context_manager(self, mock_session_class: MagicMock) -> None:
        """Test context manager usage."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_session.request.return_value = mock_response

        with InternalAPIClient(api_token="test-token") as client:
            result = client.get("/test")

        self.assertEqual(result, {"data": "value"})
        mock_session.close.assert_called_once()

    @patch("src.api.client.requests.Session")
    def test_extract_error_detail_with_detail_key(self, mock_session_class: MagicMock) -> None:
        """Test error detail extraction with detail key."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Validation error"}
        mock_session.request.return_value = mock_response

        client = InternalAPIClient(api_token="test-token")

        with self.assertRaises(InternalAPIClientError) as ctx:
            client.post("/test")

        self.assertIn("Validation error", str(ctx.exception))

    @patch("src.api.client.requests.Session")
    def test_extract_error_detail_with_text_fallback(self, mock_session_class: MagicMock) -> None:
        """Test error detail extraction falls back to text."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Internal Server Error"
        mock_session.request.return_value = mock_response

        client = InternalAPIClient(api_token="test-token")

        with self.assertRaises(InternalAPIClientError) as ctx:
            client.get("/test")

        self.assertIn("Internal Server Error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
