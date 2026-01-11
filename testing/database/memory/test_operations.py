"""Tests for agent memory database operations."""

import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import NoResultFound

from src.agent.enums import MemoryCategory
from src.database.memory import (
    AgentMemory,
    AgentMemoryVersion,
    create_memory,
    delete_memory,
    find_memory_by_subject,
    get_active_memories,
    get_memory_by_id,
    get_memory_with_versions,
    update_memory,
)


class TestCreateMemory(unittest.TestCase):
    """Tests for create_memory function."""

    def test_creates_memory_with_initial_version(self) -> None:
        """Should create a memory with version 1."""
        session = MagicMock()
        session.flush = MagicMock()

        create_memory(
            session,
            content="Alec is my boss",
            category=MemoryCategory.PERSON,
            subject="Alec",
        )

        # Should add both memory and version
        self.assertEqual(session.add.call_count, 2)
        self.assertEqual(session.flush.call_count, 2)

        # Check memory
        memory_call = session.add.call_args_list[0][0][0]
        self.assertIsInstance(memory_call, AgentMemory)
        self.assertEqual(memory_call.category, MemoryCategory.PERSON)
        self.assertEqual(memory_call.subject, "Alec")

        # Check version
        version_call = session.add.call_args_list[1][0][0]
        self.assertIsInstance(version_call, AgentMemoryVersion)
        self.assertEqual(version_call.content, "Alec is my boss")
        self.assertEqual(version_call.version_number, 1)

    def test_creates_memory_without_subject(self) -> None:
        """Should create a memory without subject."""
        session = MagicMock()

        create_memory(
            session,
            content="I prefer Friday due dates",
            category=MemoryCategory.PREFERENCE,
        )

        memory_call = session.add.call_args_list[0][0][0]
        self.assertIsNone(memory_call.subject)

    def test_creates_memory_with_source_conversation(self) -> None:
        """Should create a memory with source conversation ID."""
        session = MagicMock()
        conversation_id = uuid.uuid4()

        create_memory(
            session,
            content="Test content",
            category=MemoryCategory.CONTEXT,
            source_conversation_id=conversation_id,
        )

        version_call = session.add.call_args_list[1][0][0]
        self.assertEqual(version_call.source_conversation_id, conversation_id)


class TestGetMemoryById(unittest.TestCase):
    """Tests for get_memory_by_id function."""

    def test_returns_memory_when_found(self) -> None:
        """Should return memory when it exists."""
        memory_id = "abc123de"
        expected = AgentMemory(id=memory_id, category=MemoryCategory.PERSON)

        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = expected

        result = get_memory_by_id(session, memory_id)

        self.assertEqual(result, expected)

    def test_raises_when_not_found(self) -> None:
        """Should raise NoResultFound when memory doesn't exist."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.side_effect = NoResultFound()

        with self.assertRaises(NoResultFound):
            get_memory_by_id(session, "notfound")


class TestGetMemoryWithVersions(unittest.TestCase):
    """Tests for get_memory_with_versions function."""

    def test_loads_versions_eagerly(self) -> None:
        """Should load versions relationship."""
        memory_id = "abc123de"
        memory = AgentMemory(id=memory_id, category=MemoryCategory.PERSON)

        session = MagicMock()
        query_mock = session.query.return_value
        options_mock = query_mock.options.return_value
        filter_mock = options_mock.filter.return_value
        filter_mock.one.return_value = memory

        result = get_memory_with_versions(session, memory_id)

        self.assertEqual(result, memory)
        query_mock.options.assert_called_once()


class TestGetActiveMemories(unittest.TestCase):
    """Tests for get_active_memories function."""

    def test_returns_only_active_memories(self) -> None:
        """Should filter out deleted memories."""
        active1 = AgentMemory(id="active01", category=MemoryCategory.PERSON)
        active2 = AgentMemory(id="active02", category=MemoryCategory.PREFERENCE)

        session = MagicMock()
        query_mock = session.query.return_value
        options_mock = query_mock.options.return_value
        filter_mock = options_mock.filter.return_value
        order_mock = filter_mock.order_by.return_value
        order_mock.all.return_value = [active1, active2]

        result = get_active_memories(session)

        self.assertEqual(len(result), 2)
        # Verify ordering by category and created_at
        filter_mock.order_by.assert_called_once()

    def test_orders_by_category_and_created_at(self) -> None:
        """Should order memories consistently for caching."""
        session = MagicMock()
        query_mock = session.query.return_value
        options_mock = query_mock.options.return_value
        filter_mock = options_mock.filter.return_value

        get_active_memories(session)

        # Check that order_by was called
        filter_mock.order_by.assert_called_once()


class TestUpdateMemory(unittest.TestCase):
    """Tests for update_memory function."""

    @patch("src.database.memory.operations.get_memory_with_versions")
    def test_creates_new_version(self, mock_get: MagicMock) -> None:
        """Should create a new version with incremented number."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        version1 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=1,
            content="Old content",
        )
        memory.versions = [version1]
        mock_get.return_value = memory

        session = MagicMock()

        update_memory(session, "mem12345", "New content")

        # Should add new version
        session.add.assert_called_once()
        new_version = session.add.call_args[0][0]
        self.assertIsInstance(new_version, AgentMemoryVersion)
        self.assertEqual(new_version.version_number, 2)
        self.assertEqual(new_version.content, "New content")

    @patch("src.database.memory.operations.get_memory_with_versions")
    def test_raises_on_deleted_memory(self, mock_get: MagicMock) -> None:
        """Should raise ValueError when updating deleted memory."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        memory.deleted_at = datetime.now()
        mock_get.return_value = memory

        session = MagicMock()

        with self.assertRaises(ValueError):
            update_memory(session, "mem12345", "New content")

    @patch("src.database.memory.operations.get_memory_with_versions")
    def test_updates_subject_when_provided(self, mock_get: MagicMock) -> None:
        """Should update subject when provided."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON, subject="Alec")
        version1 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=1,
            content="Alec is my boss",
        )
        memory.versions = [version1]
        mock_get.return_value = memory

        session = MagicMock()

        update_memory(session, "mem12345", "Seabrook is my boss", subject="Seabrook")

        self.assertEqual(memory.subject, "Seabrook")

    @patch("src.database.memory.operations.get_memory_with_versions")
    def test_includes_source_conversation(self, mock_get: MagicMock) -> None:
        """Should include source conversation ID in new version."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        version1 = AgentMemoryVersion(
            memory_id="mem12345",
            version_number=1,
            content="Old content",
        )
        memory.versions = [version1]
        mock_get.return_value = memory

        session = MagicMock()
        conversation_id = uuid.uuid4()

        update_memory(session, "mem12345", "New content", source_conversation_id=conversation_id)

        new_version = session.add.call_args[0][0]
        self.assertEqual(new_version.source_conversation_id, conversation_id)


class TestDeleteMemory(unittest.TestCase):
    """Tests for delete_memory function."""

    @patch("src.database.memory.operations.get_memory_by_id")
    def test_sets_deleted_at_timestamp(self, mock_get: MagicMock) -> None:
        """Should set deleted_at to current time."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        mock_get.return_value = memory

        session = MagicMock()

        result = delete_memory(session, "mem12345")

        self.assertIsNotNone(result.deleted_at)
        self.assertIsInstance(result.deleted_at, datetime)
        session.flush.assert_called_once()


class TestFindMemoryBySubject(unittest.TestCase):
    """Tests for find_memory_by_subject function."""

    def test_returns_memory_when_found(self) -> None:
        """Should return active memory with matching subject."""
        expected = AgentMemory(id="mem12345", category=MemoryCategory.PERSON, subject="Alec")

        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = expected

        result = find_memory_by_subject(session, "Alec")

        self.assertEqual(result, expected)

    def test_returns_none_when_not_found(self) -> None:
        """Should return None when subject doesn't exist."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.side_effect = NoResultFound()

        result = find_memory_by_subject(session, "NonExistent")

        self.assertIsNone(result)


class TestMemoryModelProperties(unittest.TestCase):
    """Tests for AgentMemory model properties."""

    def test_is_active_when_not_deleted(self) -> None:
        """Should return True when deleted_at is None."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)

        self.assertTrue(memory.is_active)

    def test_is_not_active_when_deleted(self) -> None:
        """Should return False when deleted_at is set."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        memory.deleted_at = datetime.now()

        self.assertFalse(memory.is_active)

    def test_current_content_returns_latest_version(self) -> None:
        """Should return content from most recent version."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        v1 = AgentMemoryVersion(memory_id="mem12345", version_number=1, content="Old")
        v2 = AgentMemoryVersion(memory_id="mem12345", version_number=2, content="New")
        memory.versions = [v1, v2]

        self.assertEqual(memory.current_content, "New")

    def test_current_content_returns_none_when_no_versions(self) -> None:
        """Should return None when no versions exist."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        memory.versions = []

        self.assertIsNone(memory.current_content)

    def test_current_version_returns_latest(self) -> None:
        """Should return most recent version object."""
        memory = AgentMemory(id="mem12345", category=MemoryCategory.PERSON)
        v1 = AgentMemoryVersion(memory_id="mem12345", version_number=1, content="Old")
        v2 = AgentMemoryVersion(memory_id="mem12345", version_number=2, content="New")
        memory.versions = [v1, v2]

        self.assertEqual(memory.current_version, v2)


if __name__ == "__main__":
    unittest.main()
