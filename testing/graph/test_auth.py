"""Tests for Graph API authentication module."""

import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.graph.auth import (
    DEFAULT_REQUEST_TIMEOUT,
    GraphAPI,
    GraphAuthenticationError,
)


class TestGraphAPIInitialisation(unittest.TestCase):
    """Tests for GraphAPI initialisation."""

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_initialisation_with_required_env_vars(
        self,
        mock_app: MagicMock,
    ) -> None:
        """Test successful initialisation with required environment variables."""
        client = GraphAPI("user@example.com")

        self.assertEqual(client._target_upn, "user@example.com")
        self.assertEqual(client._tenant_id, "test-tenant")
        self.assertEqual(client._client_id, "test-app")
        self.assertEqual(client._cache_file, Path("msal_cache.bin"))

    @patch.dict("os.environ", {}, clear=True)
    def test_initialisation_missing_tenant_id_raises_key_error(self) -> None:
        """Test initialisation fails when GRAPH_TENANT_ID is missing."""
        with self.assertRaises(KeyError) as context:
            GraphAPI("user@example.com")

        self.assertIn("GRAPH_TENANT_ID", str(context.exception))

    @patch.dict("os.environ", {"GRAPH_TENANT_ID": "test-tenant"}, clear=True)
    def test_initialisation_missing_application_id_raises_key_error(self) -> None:
        """Test initialisation fails when GRAPH_APPLICATION_ID is missing."""
        with self.assertRaises(KeyError) as context:
            GraphAPI("user@example.com")

        self.assertIn("GRAPH_APPLICATION_ID", str(context.exception))

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_initialisation_with_custom_cache_file(
        self,
        mock_app: MagicMock,
    ) -> None:
        """Test initialisation with custom cache file path."""
        custom_path = Path("/tmp/custom_cache.bin")
        client = GraphAPI("user@example.com", cache_file=custom_path)

        self.assertEqual(client._cache_file, custom_path)


class TestGraphAPICache(unittest.TestCase):
    """Tests for GraphAPI cache operations."""

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_load_cache_creates_new_cache_when_file_missing(
        self,
        mock_app: MagicMock,
    ) -> None:
        """Test cache loading creates new cache when file does not exist."""
        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")
            cache = client._load_cache()

            self.assertIsNotNone(cache)
            self.assertEqual(client._cache, cache)

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_load_cache_deserialises_existing_cache(
        self,
        mock_app: MagicMock,
    ) -> None:
        """Test cache loading deserialises existing cache file."""
        cache_data = '{"some": "data"}'

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=cache_data),
        ):
            client = GraphAPI("user@example.com")
            # Reset cache to force reload
            client._cache = None
            cache = client._load_cache()

            self.assertIsNotNone(cache)

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_save_cache_raises_when_not_initialised(
        self,
        mock_app: MagicMock,
    ) -> None:
        """Test saving cache raises ValueError when cache is not initialised."""
        client = GraphAPI("user@example.com")
        client._cache = None

        with self.assertRaises(ValueError) as context:
            client._save_cache()

        self.assertIn("not initialised", str(context.exception))

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_save_cache_writes_when_state_changed(
        self,
        mock_app: MagicMock,
    ) -> None:
        """Test saving cache writes to file when state has changed."""
        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._cache.has_state_changed = True

        with patch.object(Path, "write_text") as mock_write:
            client._save_cache()
            mock_write.assert_called_once()


class TestGraphAPITokenAcquisition(unittest.TestCase):
    """Tests for GraphAPI token acquisition."""

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_access_token_silent_success(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test silent token acquisition succeeds with cached account."""
        mock_app = mock_app_class.return_value
        mock_app.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_app.acquire_token_silent.return_value = {
            "access_token": "test-token",
            "expires_in": 3600,
        }

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        with patch.object(Path, "write_text"):
            token = client._get_access_token()

        self.assertEqual(token, "test-token")
        self.assertEqual(client._access_token, "test-token")
        mock_app.initiate_device_flow.assert_not_called()

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_access_token_device_flow_success(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test device flow token acquisition succeeds when silent fails."""
        mock_app = mock_app_class.return_value
        mock_app.get_accounts.return_value = []
        mock_app.initiate_device_flow.return_value = {
            "user_code": "ABC123",
            "message": "Go to https://example.com and enter ABC123",
        }
        mock_app.acquire_token_by_device_flow.return_value = {
            "access_token": "device-token",
            "expires_in": 3600,
        }

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        with patch.object(Path, "write_text"):
            token = client._get_access_token()

        self.assertEqual(token, "device-token")

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_access_token_device_flow_initiation_fails(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test device flow raises error when initiation fails."""
        mock_app = mock_app_class.return_value
        mock_app.get_accounts.return_value = []
        mock_app.initiate_device_flow.return_value = {
            "error": "some_error",
            "error_description": "Device flow failed",
        }

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        with self.assertRaises(GraphAuthenticationError) as context:
            client._get_access_token()

        self.assertIn("Failed to initiate device flow", str(context.exception))

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_access_token_acquisition_fails(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test token acquisition raises error when it fails."""
        mock_app = mock_app_class.return_value
        mock_app.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_app.acquire_token_silent.return_value = {
            "error": "invalid_grant",
            "error_description": "Token expired",
        }
        mock_app.initiate_device_flow.return_value = {
            "user_code": "ABC123",
            "message": "Go to URL",
        }
        mock_app.acquire_token_by_device_flow.return_value = {
            "error": "authorization_declined",
            "error_description": "User declined",
        }

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        with (
            patch.object(Path, "write_text"),
            self.assertRaises(GraphAuthenticationError) as context,
        ):
            client._get_access_token()

        self.assertIn("Failed to acquire token", str(context.exception))


class TestGraphAPIAccessTokenProperty(unittest.TestCase):
    """Tests for GraphAPI access_token property."""

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_access_token_returns_cached_token_when_valid(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test access_token returns cached token when not expired."""
        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "cached-token"
        client._access_expires = datetime.now(UTC) + timedelta(hours=1)

        token = client.access_token

        self.assertEqual(token, "cached-token")

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_access_token_refreshes_when_expired(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test access_token refreshes token when expired."""
        mock_app = mock_app_class.return_value
        mock_app.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_app.acquire_token_silent.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "old-token"
        client._access_expires = datetime.now(UTC) - timedelta(hours=1)

        with patch.object(Path, "write_text"):
            token = client.access_token

        self.assertEqual(token, "new-token")

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.PublicClientApplication")
    def test_access_token_raises_when_expiry_not_set(
        self,
        mock_app_class: MagicMock,
    ) -> None:
        """Test access_token raises RuntimeError when expiry is not set."""
        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "some-token"
        client._access_expires = None

        with self.assertRaises(RuntimeError) as context:
            _ = client.access_token

        self.assertIn("expiration not set", str(context.exception))


class TestGraphAPIRequests(unittest.TestCase):
    """Tests for GraphAPI HTTP requests."""

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.requests.get")
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_request_success(
        self,
        mock_app_class: MagicMock,
        mock_requests_get: MagicMock,
    ) -> None:
        """Test successful GET request to Graph API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "test-token"
        client._access_expires = datetime.now(UTC) + timedelta(hours=1)

        response = client.get("messages")

        mock_requests_get.assert_called_once_with(
            "https://graph.microsoft.com/v1.0/users/user@example.com/messages",
            headers={"Authorization": "Bearer test-token"},
            params=None,
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )
        self.assertEqual(response.status_code, 200)

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.requests.get")
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_request_with_params(
        self,
        mock_app_class: MagicMock,
        mock_requests_get: MagicMock,
    ) -> None:
        """Test GET request with query parameters."""
        mock_requests_get.return_value = MagicMock()

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "test-token"
        client._access_expires = datetime.now(UTC) + timedelta(hours=1)

        params = {"$top": "10", "$filter": "isRead eq false"}
        client.get("messages", params=params)

        mock_requests_get.assert_called_once()
        call_kwargs = mock_requests_get.call_args.kwargs
        self.assertEqual(call_kwargs["params"], params)

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.requests.get")
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_request_strips_slashes_from_endpoint(
        self,
        mock_app_class: MagicMock,
        mock_requests_get: MagicMock,
    ) -> None:
        """Test GET request strips leading/trailing slashes from endpoint."""
        mock_requests_get.return_value = MagicMock()

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "test-token"
        client._access_expires = datetime.now(UTC) + timedelta(hours=1)

        client.get("/messages/")

        call_args = mock_requests_get.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        self.assertTrue(url.endswith("/messages"))
        self.assertNotIn("//messages", url)

    @patch.dict(
        "os.environ",
        {"GRAPH_TENANT_ID": "test-tenant", "GRAPH_APPLICATION_ID": "test-app"},
    )
    @patch("src.graph.auth.requests.get")
    @patch("src.graph.auth.PublicClientApplication")
    def test_get_request_with_custom_timeout(
        self,
        mock_app_class: MagicMock,
        mock_requests_get: MagicMock,
    ) -> None:
        """Test GET request with custom timeout."""
        mock_requests_get.return_value = MagicMock()

        with patch.object(Path, "exists", return_value=False):
            client = GraphAPI("user@example.com")

        client._access_token = "test-token"
        client._access_expires = datetime.now(UTC) + timedelta(hours=1)

        client.get("messages", timeout=60)

        call_kwargs = mock_requests_get.call_args.kwargs
        self.assertEqual(call_kwargs["timeout"], 60)


if __name__ == "__main__":
    unittest.main()
