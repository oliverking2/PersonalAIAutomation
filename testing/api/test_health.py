"""Tests for health check endpoints."""


# Set required environment variables before importing API modules

import unittest

from fastapi.testclient import TestClient

from src.api.app import app


class TestHealthEndpoint(unittest.TestCase):
    """Tests for /health endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)

    def test_health_check_returns_200(self) -> None:
        """Test that health check returns 200 OK."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_healthy_status(self) -> None:
        """Test that health check returns healthy status."""
        response = self.client.get("/health")
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)

    def test_health_check_returns_version(self) -> None:
        """Test that health check returns version string."""
        response = self.client.get("/health")
        data = response.json()
        self.assertEqual(data["version"], "0.1.0")


if __name__ == "__main__":
    unittest.main()
