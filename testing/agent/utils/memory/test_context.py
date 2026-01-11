"""Tests for memory context building utilities."""

import unittest
from datetime import UTC, datetime

from src.agent.enums import MemoryCategory
from src.agent.utils.memory.context import build_memory_context
from src.database.memory.models import AgentMemory, AgentMemoryVersion


class TestBuildMemoryContext(unittest.TestCase):
    """Tests for build_memory_context function."""

    def _create_memory(
        self,
        memory_id: str,
        category: str,
        content: str,
        subject: str | None = None,
    ) -> AgentMemory:
        """Create a memory with a version for testing.

        :param memory_id: Memory ID.
        :param category: Category string.
        :param content: Content string.
        :param subject: Optional subject.
        :returns: AgentMemory instance with version.
        """
        memory = AgentMemory(
            id=memory_id,
            category=category,
            subject=subject,
            created_at=datetime.now(UTC),
        )
        version = AgentMemoryVersion(
            memory_id=memory_id,
            version_number=1,
            content=content,
            created_at=datetime.now(UTC),
        )
        memory.versions = [version]
        return memory

    def test_empty_memories_returns_empty_string(self) -> None:
        """Test that empty list returns empty string."""
        result = build_memory_context([])
        self.assertEqual(result, "")

    def test_single_memory_formats_correctly(self) -> None:
        """Test formatting of a single memory."""
        memory = self._create_memory(
            "abc12345",
            MemoryCategory.PERSON,
            "Alec is my boss at TechCorp",
            "Alec",
        )

        result = build_memory_context([memory])

        self.assertIn("## Your Memory", result)
        self.assertIn("### Person", result)
        self.assertIn("[id:abc12345]", result)
        self.assertIn("[Alec]", result)
        self.assertIn("Alec is my boss at TechCorp", result)

    def test_memory_without_subject(self) -> None:
        """Test formatting of memory without subject."""
        memory = self._create_memory(
            "pref1234",
            MemoryCategory.PREFERENCE,
            "I prefer Friday due dates",
        )

        result = build_memory_context([memory])

        self.assertIn("[id:pref1234]", result)
        self.assertIn("I prefer Friday due dates", result)
        # Should not have subject brackets
        self.assertNotIn("[]", result)

    def test_multiple_categories_grouped(self) -> None:
        """Test that memories are grouped by category."""
        person = self._create_memory(
            "person01",
            MemoryCategory.PERSON,
            "Alec is my boss",
            "Alec",
        )
        preference = self._create_memory(
            "pref0001",
            MemoryCategory.PREFERENCE,
            "I prefer Friday due dates",
        )
        context = self._create_memory(
            "context1",
            MemoryCategory.CONTEXT,
            "I work on the Platform team",
        )

        result = build_memory_context([person, preference, context])

        # All categories should appear
        self.assertIn("### Person", result)
        self.assertIn("### Preference", result)
        self.assertIn("### Context", result)

        # Content should be present
        self.assertIn("Alec is my boss", result)
        self.assertIn("I prefer Friday due dates", result)
        self.assertIn("I work on the Platform team", result)

    def test_categories_sorted_alphabetically(self) -> None:
        """Test that categories appear in alphabetical order."""
        preference = self._create_memory(
            "pref0001",
            MemoryCategory.PREFERENCE,
            "I prefer Friday due dates",
        )
        context = self._create_memory(
            "context1",
            MemoryCategory.CONTEXT,
            "I work on the Platform team",
        )

        result = build_memory_context([preference, context])

        # Context should appear before Preference (alphabetically)
        context_pos = result.find("### Context")
        preference_pos = result.find("### Preference")

        self.assertLess(context_pos, preference_pos)

    def test_includes_instructions(self) -> None:
        """Test that output includes usage instructions."""
        memory = self._create_memory(
            "test0001",
            MemoryCategory.CONTEXT,
            "Test content",
        )

        result = build_memory_context([memory])

        self.assertIn("information you've learned", result.lower())
        self.assertIn("update_memory", result)

    def test_multiple_memories_same_category(self) -> None:
        """Test multiple memories in same category."""
        alec = self._create_memory(
            "person01",
            MemoryCategory.PERSON,
            "Alec is my boss",
            "Alec",
        )
        sarah = self._create_memory(
            "person02",
            MemoryCategory.PERSON,
            "Sarah is on the Design team",
            "Sarah",
        )

        result = build_memory_context([alec, sarah])

        # Only one Person header
        self.assertEqual(result.count("### Person"), 1)

        # Both memories present
        self.assertIn("[id:person01]", result)
        self.assertIn("[id:person02]", result)
        self.assertIn("Alec is my boss", result)
        self.assertIn("Sarah is on the Design team", result)


if __name__ == "__main__":
    unittest.main()
