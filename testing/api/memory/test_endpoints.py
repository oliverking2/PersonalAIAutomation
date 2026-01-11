"""Tests for memory API endpoints."""

import os

# Set required environment variables before importing API modules
os.environ.setdefault("API_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("NOTION_INTEGRATION_SECRET", "test-notion-token")
os.environ.setdefault("NOTION_TASK_DATA_SOURCE_ID", "test-data-source-id")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456789")

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import NoResultFound

from src.agent.enums import MemoryCategory
from src.api.app import app
from src.database.memory.models import AgentMemory, AgentMemoryVersion


class TestListMemoriesEndpoint(unittest.TestCase):
    """Tests for GET /memory endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.memory.endpoints.get_session")
    def test_list_memories_success(self, mock_get_session: MagicMock) -> None:
        """Test successful listing of memories."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        memory1 = AgentMemory(
            id="mem12345",
            category=MemoryCategory.PERSON,
            subject="Alec",
            created_at=datetime.now(UTC),
        )
        version1 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=1,
            content="Alec is my boss",
            created_at=datetime.now(UTC),
        )
        memory1.versions = [version1]

        with patch("src.api.memory.endpoints.get_active_memories") as mock_get:
            mock_get.return_value = [memory1]

            response = self.client.get("/memory", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["memories"]), 1)
        self.assertEqual(data["memories"][0]["id"], "mem12345")
        self.assertEqual(data["memories"][0]["content"], "Alec is my boss")

    @patch("src.api.memory.endpoints.get_session")
    def test_list_memories_empty(self, mock_get_session: MagicMock) -> None:
        """Test listing when no memories exist."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.memory.endpoints.get_active_memories") as mock_get:
            mock_get.return_value = []

            response = self.client.get("/memory", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["memories"]), 0)


class TestGetMemoryEndpoint(unittest.TestCase):
    """Tests for GET /memory/{id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.memory.endpoints.get_session")
    def test_get_memory_success(self, mock_get_session: MagicMock) -> None:
        """Test successful retrieval of memory with versions."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        memory = AgentMemory(
            id="mem12345",
            category=MemoryCategory.PERSON,
            subject="Sarah",
            created_at=datetime.now(UTC),
        )
        v1 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=1,
            content="Sarah works on Platform team",
            created_at=datetime.now(UTC),
        )
        v2 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=2,
            content="Sarah works on Design team",
            created_at=datetime.now(UTC),
        )
        memory.versions = [v1, v2]

        with patch("src.api.memory.endpoints.get_memory_with_versions") as mock_get:
            mock_get.return_value = memory

            response = self.client.get("/memory/mem12345", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "mem12345")
        self.assertEqual(len(data["versions"]), 2)
        self.assertEqual(data["versions"][0]["content"], "Sarah works on Platform team")
        self.assertEqual(data["versions"][1]["content"], "Sarah works on Design team")

    @patch("src.api.memory.endpoints.get_session")
    def test_get_memory_not_found(self, mock_get_session: MagicMock) -> None:
        """Test 404 when memory doesn't exist."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.memory.endpoints.get_memory_with_versions") as mock_get:
            mock_get.side_effect = NoResultFound()

            response = self.client.get("/memory/notfound", headers=self.auth_headers)

        self.assertEqual(response.status_code, 404)


class TestCreateMemoryEndpoint(unittest.TestCase):
    """Tests for POST /memory endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.memory.endpoints.get_session")
    def test_create_memory_success(self, mock_get_session: MagicMock) -> None:
        """Test successful memory creation."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        memory = AgentMemory(
            id="mem12345",
            category=MemoryCategory.PERSON,
            subject="Alec",
            created_at=datetime.now(UTC),
        )
        version = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=1,
            content="Alec is my boss",
            created_at=datetime.now(UTC),
        )
        memory.versions = [version]

        with (
            patch("src.api.memory.endpoints.find_memory_by_subject") as mock_find,
            patch("src.api.memory.endpoints.create_memory") as mock_create,
        ):
            mock_find.return_value = None
            mock_create.return_value = memory

            response = self.client.post(
                "/memory",
                headers=self.auth_headers,
                json={
                    "content": "Alec is my boss",
                    "category": "person",
                    "subject": "Alec",
                },
            )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "mem12345")
        self.assertEqual(data["content"], "Alec is my boss")

    @patch("src.api.memory.endpoints.get_session")
    def test_create_memory_duplicate_subject(self, mock_get_session: MagicMock) -> None:
        """Test 409 when memory with same subject exists."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        existing = AgentMemory(
            id="existing1",
            category=MemoryCategory.PERSON,
            subject="Alec",
            created_at=datetime.now(UTC),
        )

        with patch("src.api.memory.endpoints.find_memory_by_subject") as mock_find:
            mock_find.return_value = existing

            response = self.client.post(
                "/memory",
                headers=self.auth_headers,
                json={
                    "content": "Alec is my manager",
                    "category": "person",
                    "subject": "Alec",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])


class TestUpdateMemoryEndpoint(unittest.TestCase):
    """Tests for PATCH /memory/{id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.memory.endpoints.get_session")
    def test_update_memory_success(self, mock_get_session: MagicMock) -> None:
        """Test successful memory update."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        memory = AgentMemory(
            id="mem12345",
            category=MemoryCategory.PERSON,
            subject="Sarah",
            created_at=datetime.now(UTC),
        )
        v2 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=2,
            content="Sarah works on Design team",
            created_at=datetime.now(UTC),
        )
        memory.versions = [v2]

        with patch("src.api.memory.endpoints.update_memory") as mock_update:
            mock_update.return_value = memory

            response = self.client.patch(
                "/memory/mem12345",
                headers=self.auth_headers,
                json={"content": "Sarah works on Design team"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["content"], "Sarah works on Design team")

    @patch("src.api.memory.endpoints.get_session")
    def test_update_memory_not_found(self, mock_get_session: MagicMock) -> None:
        """Test 404 when memory doesn't exist."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.memory.endpoints.update_memory") as mock_update:
            mock_update.side_effect = NoResultFound()

            response = self.client.patch(
                "/memory/notfound",
                headers=self.auth_headers,
                json={"content": "New content"},
            )

        self.assertEqual(response.status_code, 404)


class TestDeleteMemoryEndpoint(unittest.TestCase):
    """Tests for DELETE /memory/{id} endpoint."""

    def setUp(self) -> None:
        """Set up test client."""
        self.app = app
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": "Bearer test-auth-token"}

    @patch("src.api.memory.endpoints.get_session")
    def test_delete_memory_success(self, mock_get_session: MagicMock) -> None:
        """Test successful memory deletion."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.memory.endpoints.delete_memory") as mock_delete:
            mock_delete.return_value = MagicMock()

            response = self.client.delete("/memory/mem12345", headers=self.auth_headers)

        self.assertEqual(response.status_code, 204)

    @patch("src.api.memory.endpoints.get_session")
    def test_delete_memory_not_found(self, mock_get_session: MagicMock) -> None:
        """Test 404 when memory doesn't exist."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.memory.endpoints.delete_memory") as mock_delete:
            mock_delete.side_effect = NoResultFound()

            response = self.client.delete("/memory/notfound", headers=self.auth_headers)

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
