"""Tests for Substack user module."""

import unittest
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import requests

from src.substack.user import User, resolve_handle_redirect


class TestResolveHandleRedirect(unittest.TestCase):
    """Tests for resolve_handle_redirect function."""

    @patch("src.substack.user.requests.get")
    def test_returns_new_handle_when_redirected(self, mock_get: MagicMock) -> None:
        """Test that new handle is returned when redirect detected."""
        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.url = "https://substack.com/@newhandle/about"
        mock_get.return_value = mock_response

        result = resolve_handle_redirect("oldhandle")

        self.assertEqual(result, "newhandle")
        mock_get.assert_called_once()

    @patch("src.substack.user.requests.get")
    def test_returns_none_when_no_redirect(self, mock_get: MagicMock) -> None:
        """Test that None is returned when no redirect occurs."""
        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.url = "https://substack.com/@samehandle"
        mock_get.return_value = mock_response

        result = resolve_handle_redirect("samehandle")

        self.assertIsNone(result)

    @patch("src.substack.user.requests.get")
    def test_returns_none_on_request_error(self, mock_get: MagicMock) -> None:
        """Test that None is returned on request error."""
        mock_get.side_effect = requests.RequestException("Connection error")

        result = resolve_handle_redirect("anyhandle")

        self.assertIsNone(result)

    @patch("src.substack.user.requests.get")
    def test_returns_none_on_non_200_status(self, mock_get: MagicMock) -> None:
        """Test that None is returned on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.NOT_FOUND
        mock_get.return_value = mock_response

        result = resolve_handle_redirect("unknownhandle")

        self.assertIsNone(result)


class TestUser(unittest.TestCase):
    """Tests for User class."""

    def test_init_sets_username(self) -> None:
        """Test that initialisation sets username correctly."""
        user = User("testuser")

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.original_username, "testuser")
        self.assertTrue(user.follow_redirects)

    def test_str_representation(self) -> None:
        """Test string representation."""
        user = User("testuser")

        self.assertEqual(str(user), "User: testuser")

    def test_repr_representation(self) -> None:
        """Test repr representation."""
        user = User("testuser")

        self.assertEqual(repr(user), "User(username='testuser')")

    @patch("src.substack.user.requests.get")
    def test_fetch_user_data_caches_result(self, mock_get: MagicMock) -> None:
        """Test that user data is cached after first fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "name": "Test User"}
        mock_get.return_value = mock_response

        user = User("testuser")
        user._fetch_user_data()
        user._fetch_user_data()

        mock_get.assert_called_once()

    @patch("src.substack.user.requests.get")
    def test_fetch_user_data_force_refresh(self, mock_get: MagicMock) -> None:
        """Test that force_refresh bypasses cache."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "name": "Test User"}
        mock_get.return_value = mock_response

        user = User("testuser")
        user._fetch_user_data()
        user._fetch_user_data(force_refresh=True)

        self.assertEqual(mock_get.call_count, 2)

    @patch("src.substack.user.requests.get")
    def test_id_property(self, mock_get: MagicMock) -> None:
        """Test id property returns user ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 12345, "name": "Test"}
        mock_get.return_value = mock_response

        user = User("testuser")

        self.assertEqual(user.id, 12345)

    @patch("src.substack.user.requests.get")
    def test_name_property(self, mock_get: MagicMock) -> None:
        """Test name property returns user name."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "name": "Test User"}
        mock_get.return_value = mock_response

        user = User("testuser")

        self.assertEqual(user.name, "Test User")

    @patch("src.substack.user.requests.get")
    def test_get_subscriptions(self, mock_get: MagicMock) -> None:
        """Test get_subscriptions returns formatted subscription list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "Test",
            "subscriptions": [
                {
                    "publication": {
                        "id": 1,
                        "name": "Newsletter One",
                        "subdomain": "newsletter1",
                        "custom_domain": None,
                    },
                    "membership_state": "active",
                },
                {
                    "publication": {
                        "id": 2,
                        "name": "Newsletter Two",
                        "subdomain": "newsletter2",
                        "custom_domain": "newsletter2.com",
                    },
                    "membership_state": "active",
                },
            ],
        }
        mock_get.return_value = mock_response

        user = User("testuser")
        subs = user.get_subscriptions()

        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0]["publication_name"], "Newsletter One")
        self.assertEqual(subs[0]["domain"], "newsletter1.substack.com")
        self.assertEqual(subs[1]["domain"], "newsletter2.com")

    def test_was_redirected_false_initially(self) -> None:
        """Test was_redirected is False when no redirect occurred."""
        user = User("testuser")

        self.assertFalse(user.was_redirected)

    @patch("src.substack.user.resolve_handle_redirect")
    @patch("src.substack.user.requests.get")
    def test_handles_404_with_redirect(self, mock_get: MagicMock, mock_resolve: MagicMock) -> None:
        """Test that 404 errors trigger redirect resolution."""
        # First call raises 404, second succeeds
        http_error = requests.HTTPError()
        http_error.response = MagicMock()
        http_error.response.status_code = HTTPStatus.NOT_FOUND

        success_response = MagicMock()
        success_response.json.return_value = {"id": 123, "name": "New User"}

        mock_get.side_effect = [http_error, success_response]
        mock_resolve.return_value = "newhandle"

        user = User("oldhandle")
        data = user._fetch_user_data()

        self.assertEqual(user.username, "newhandle")
        self.assertEqual(data["id"], 123)
        self.assertTrue(user.was_redirected)


if __name__ == "__main__":
    unittest.main()
