"""Tests for extraction state operations."""

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.database.extraction_state import get_watermark, set_watermark
from src.database.extraction_state.models import ExtractionState


class TestGetWatermark(unittest.TestCase):
    """Tests for get_watermark function."""

    def test_returns_none_when_no_state_exists(self) -> None:
        """Should return None when no extraction state exists for the source."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        result = get_watermark(session, "test:source")

        self.assertIsNone(result)

    def test_returns_watermark_when_state_exists(self) -> None:
        """Should return the watermark datetime when state exists."""
        expected_watermark = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        state = MagicMock()
        state.watermark = expected_watermark

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = state

        result = get_watermark(session, "test:source")

        self.assertEqual(result, expected_watermark)


class TestSetWatermark(unittest.TestCase):
    """Tests for set_watermark function."""

    def test_creates_new_state_when_none_exists(self) -> None:
        """Should create a new extraction state when none exists."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        watermark = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        set_watermark(session, "test:source", watermark)

        session.add.assert_called_once()
        session.flush.assert_called_once()

        # Verify the created state
        added_state = session.add.call_args[0][0]
        self.assertIsInstance(added_state, ExtractionState)
        self.assertEqual(added_state.source_id, "test:source")
        self.assertEqual(added_state.watermark, watermark)

    def test_updates_existing_state(self) -> None:
        """Should update existing state when it exists."""
        existing_state = MagicMock()
        existing_state.watermark = datetime(2024, 1, 10, 0, 0, 0, tzinfo=UTC)

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = existing_state

        new_watermark = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        set_watermark(session, "test:source", new_watermark)

        self.assertEqual(existing_state.watermark, new_watermark)
        session.add.assert_not_called()
        session.flush.assert_called_once()

    def test_raises_error_for_naive_datetime(self) -> None:
        """Should raise ValueError when watermark is not timezone-aware."""
        session = MagicMock()
        naive_watermark = datetime(2024, 1, 15, 10, 30, 0)

        with self.assertRaises(ValueError) as context:
            set_watermark(session, "test:source", naive_watermark)

        self.assertIn("timezone-aware", str(context.exception))


class TestExtractionStateModel(unittest.TestCase):
    """Tests for ExtractionState model."""

    def test_repr(self) -> None:
        """Should return a readable string representation."""
        watermark = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        state = ExtractionState(source_id="test:source", watermark=watermark)

        result = repr(state)

        self.assertIn("test:source", result)
        self.assertIn("ExtractionState", result)


if __name__ == "__main__":
    unittest.main()
