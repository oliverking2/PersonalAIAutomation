"""Tests for API dependencies module."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.security import get_api_token, verify_token


class TestGetApiToken(unittest.TestCase):
    """Tests for get_api_token function."""

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "test-token"})
    def test_returns_token_from_environment(self) -> None:
        """Test that token is retrieved from environment variable."""
        token = get_api_token()
        self.assertEqual(token, "test-token")

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_value_error_when_not_set(self) -> None:
        """Test that ValueError is raised when token is not configured."""
        os.environ.pop("API_AUTH_TOKEN", None)
        with self.assertRaises(ValueError) as context:
            get_api_token()
        self.assertIn("API_AUTH_TOKEN", str(context.exception))


class TestVerifyToken(unittest.TestCase):
    """Tests for verify_token dependency."""

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "valid-token"})
    def test_valid_token_returns_token(self) -> None:
        """Test that valid token passes verification."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-token",
        )
        result = verify_token(credentials)
        self.assertEqual(result, "valid-token")

    @patch.dict(os.environ, {"API_AUTH_TOKEN": "valid-token"})
    def test_invalid_token_raises_401(self) -> None:
        """Test that invalid token raises HTTPException with 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="wrong-token",
        )
        with self.assertRaises(HTTPException) as context:
            verify_token(credentials)
        self.assertEqual(context.exception.status_code, 401)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_config_raises_500(self) -> None:
        """Test that missing configuration raises HTTPException with 500."""
        os.environ.pop("API_AUTH_TOKEN", None)
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="any-token",
        )
        with self.assertRaises(HTTPException) as context:
            verify_token(credentials)
        self.assertEqual(context.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()
