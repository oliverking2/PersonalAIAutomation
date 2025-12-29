"""Tests for Substack client."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.substack.client import SubstackClient


class TestSubstackClient(unittest.TestCase):
    """Tests for SubstackClient class."""

    def test_init_without_cookies(self) -> None:
        """Test initialisation without cookies path (no default file exists)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_path = Path(tmpdir) / ".substack" / "cookies.json"
            with patch("src.substack.client.PROJECT_ROOT", Path(tmpdir)):
                client = SubstackClient()

                self.assertEqual(client.cookies_path, nonexistent_path)
                self.assertFalse(client.authenticated)
                self.assertTrue(client.rate_limit)

    def test_init_with_missing_cookies_file(self) -> None:
        """Test initialisation with missing cookies file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_path = Path(tmpdir) / "missing.json"

            client = SubstackClient(cookies_path=cookies_path)

            self.assertFalse(client.authenticated)
            self.assertEqual(len(client.session.cookies), 0)

    def test_init_with_valid_cookies_file(self) -> None:
        """Test initialisation with valid cookies file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_path = Path(tmpdir) / "cookies.json"
            cookies_data = [
                {
                    "name": "session",
                    "value": "abc123",
                    "domain": ".substack.com",
                    "path": "/",
                    "secure": True,
                },
            ]
            cookies_path.write_text(json.dumps(cookies_data))

            client = SubstackClient(cookies_path=cookies_path)

            self.assertTrue(client.authenticated)
            self.assertEqual(client.session.cookies.get("session"), "abc123")

    def test_init_with_invalid_json_raises_error(self) -> None:
        """Test initialisation with invalid JSON raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_path = Path(tmpdir) / "cookies.json"
            cookies_path.write_text("not valid json")

            with self.assertRaises(ValueError) as ctx:
                SubstackClient(cookies_path=cookies_path)

            self.assertIn("Invalid cookies file", str(ctx.exception))

    def test_init_with_missing_cookie_fields_raises_error(self) -> None:
        """Test initialisation with missing required cookie fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_path = Path(tmpdir) / "cookies.json"
            # Missing 'name' field
            cookies_data = [{"value": "abc123"}]
            cookies_path.write_text(json.dumps(cookies_data))

            with self.assertRaises(ValueError):
                SubstackClient(cookies_path=cookies_path)

    def test_init_with_rate_limit_disabled(self) -> None:
        """Test initialisation with rate limiting disabled."""
        client = SubstackClient(rate_limit=False)

        self.assertFalse(client.rate_limit)

    @patch("src.substack.client.sleep")
    def test_get_applies_rate_limit(self, mock_sleep: MagicMock) -> None:
        """Test that get method applies rate limiting."""
        client = SubstackClient(rate_limit=True)

        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_get.return_value = mock_response

            client.get("https://example.com/api")

            mock_sleep.assert_called_once()

    @patch("src.substack.client.sleep")
    def test_get_skips_rate_limit_when_disabled(self, mock_sleep: MagicMock) -> None:
        """Test that get method skips rate limit when disabled."""
        client = SubstackClient(rate_limit=False)

        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_get.return_value = mock_response

            client.get("https://example.com/api")

            mock_sleep.assert_not_called()

    @patch("src.substack.client.sleep")
    def test_get_passes_params(self, mock_sleep: MagicMock) -> None:
        """Test that get method passes params correctly."""
        client = SubstackClient(rate_limit=False)

        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_get.return_value = mock_response

            client.get("https://example.com/api", params={"page": 1})

            call_kwargs = mock_get.call_args.kwargs
            self.assertEqual(call_kwargs["params"], {"page": 1})

    @patch("src.substack.client.sleep")
    def test_get_json_returns_parsed_response(self, mock_sleep: MagicMock) -> None:
        """Test that get_json returns parsed JSON response."""
        client = SubstackClient(rate_limit=False)

        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": "test"}
            mock_get.return_value = mock_response

            result = client.get_json("https://example.com/api")

            self.assertEqual(result, {"data": "test"})


if __name__ == "__main__":
    unittest.main()
