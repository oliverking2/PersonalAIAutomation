"""Tests for Notion API endpoint authentication."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")

import unittest

from fastapi.testclient import TestClient

from src.api.app import app


class TestNotionEndpointsAuthentication(unittest.TestCase):
    """Tests for Notion endpoint authentication."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = TestClient(app)

    def test_get_database_without_auth_returns_401(self) -> None:
        """Test that requests without auth token are rejected."""
        response = self.client.get("/notion/databases/db-123")
        self.assertEqual(response.status_code, 401)

    def test_get_database_with_invalid_auth_returns_401(self) -> None:
        """Test that requests with invalid auth token are rejected."""
        response = self.client.get(
            "/notion/databases/db-123",
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
