"""Tests for Telegram session manager module."""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from src.messaging.telegram.utils.session_manager import SessionManager


class TestSessionManager(unittest.TestCase):
    """Tests for SessionManager class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.session_manager = SessionManager(session_timeout_minutes=10)
        self.mock_db_session = MagicMock()

    @patch("src.messaging.telegram.utils.session_manager.expire_inactive_sessions")
    @patch("src.messaging.telegram.utils.session_manager.get_active_session_for_chat")
    @patch("src.messaging.telegram.utils.session_manager.update_session_activity")
    def test_get_or_create_session_returns_existing(
        self,
        mock_update_activity: MagicMock,
        mock_get_active: MagicMock,
        mock_expire: MagicMock,
    ) -> None:
        """Test get_or_create_session returns existing active session."""
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_get_active.return_value = mock_session

        session, is_new = self.session_manager.get_or_create_session(self.mock_db_session, "12345")

        self.assertEqual(session, mock_session)
        self.assertFalse(is_new)
        mock_expire.assert_called_once_with(self.mock_db_session, 10)
        mock_get_active.assert_called_once_with(self.mock_db_session, "12345")
        mock_update_activity.assert_called_once_with(self.mock_db_session, mock_session)

    @patch("src.messaging.telegram.utils.session_manager.expire_inactive_sessions")
    @patch("src.messaging.telegram.utils.session_manager.get_active_session_for_chat")
    @patch("src.messaging.telegram.utils.session_manager.create_telegram_session")
    def test_get_or_create_session_creates_new(
        self,
        mock_create_session: MagicMock,
        mock_get_active: MagicMock,
        mock_expire: MagicMock,
    ) -> None:
        """Test get_or_create_session creates new session without agent conversation.

        Agent conversation is created lazily when first message is processed.
        """
        mock_get_active.return_value = None

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_create_session.return_value = mock_session

        session, is_new = self.session_manager.get_or_create_session(self.mock_db_session, "12345")

        self.assertEqual(session, mock_session)
        self.assertTrue(is_new)
        mock_create_session.assert_called_once()

        # Check that the session was created WITHOUT an agent conversation (lazy)
        call_kwargs = mock_create_session.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], "12345")
        self.assertIsNone(call_kwargs["agent_conversation_id"])

    @patch("src.messaging.telegram.utils.session_manager.end_telegram_session")
    @patch("src.messaging.telegram.utils.session_manager.get_active_session_for_chat")
    @patch("src.messaging.telegram.utils.session_manager.create_telegram_session")
    def test_reset_session_ends_existing(
        self,
        mock_create_session: MagicMock,
        mock_get_active: MagicMock,
        mock_end_session: MagicMock,
    ) -> None:
        """Test reset_session ends existing session and creates new one.

        Agent conversation is NOT created during reset (lazy creation).
        """
        mock_existing = MagicMock()
        mock_existing.id = uuid.uuid4()
        mock_get_active.return_value = mock_existing

        mock_new_session = MagicMock()
        mock_new_session.id = uuid.uuid4()
        mock_create_session.return_value = mock_new_session

        session = self.session_manager.reset_session(self.mock_db_session, "12345")

        self.assertEqual(session, mock_new_session)
        mock_end_session.assert_called_once_with(self.mock_db_session, mock_existing)
        mock_create_session.assert_called_once()

        # Check session created without agent conversation
        call_kwargs = mock_create_session.call_args.kwargs
        self.assertIsNone(call_kwargs["agent_conversation_id"])

    @patch("src.messaging.telegram.utils.session_manager.end_telegram_session")
    @patch("src.messaging.telegram.utils.session_manager.get_active_session_for_chat")
    @patch("src.messaging.telegram.utils.session_manager.create_telegram_session")
    def test_reset_session_no_existing(
        self,
        mock_create_session: MagicMock,
        mock_get_active: MagicMock,
        mock_end_session: MagicMock,
    ) -> None:
        """Test reset_session works when no existing session."""
        mock_get_active.return_value = None

        mock_new_session = MagicMock()
        mock_new_session.id = uuid.uuid4()
        mock_create_session.return_value = mock_new_session

        session = self.session_manager.reset_session(self.mock_db_session, "12345")

        self.assertEqual(session, mock_new_session)
        mock_end_session.assert_not_called()

    @patch("src.messaging.telegram.utils.session_manager.create_agent_conversation")
    def test_ensure_agent_conversation_creates_when_missing(
        self,
        mock_create_conversation: MagicMock,
    ) -> None:
        """Test ensure_agent_conversation creates conversation when none exists."""
        mock_session = MagicMock()
        mock_session.agent_conversation_id = None
        mock_session.chat_id = "12345"

        mock_conversation = MagicMock()
        mock_conversation.id = uuid.uuid4()
        mock_create_conversation.return_value = mock_conversation

        result = self.session_manager.ensure_agent_conversation(self.mock_db_session, mock_session)

        self.assertEqual(result, mock_session)
        self.assertEqual(mock_session.agent_conversation_id, mock_conversation.id)
        mock_create_conversation.assert_called_once()
        self.mock_db_session.flush.assert_called_once()

    def test_ensure_agent_conversation_returns_existing(self) -> None:
        """Test ensure_agent_conversation returns session when conversation exists."""
        mock_session = MagicMock()
        mock_session.agent_conversation_id = uuid.uuid4()

        result = self.session_manager.ensure_agent_conversation(self.mock_db_session, mock_session)

        self.assertEqual(result, mock_session)
        # No flush should be called as no changes were made
        self.mock_db_session.flush.assert_not_called()

    def test_custom_session_timeout(self) -> None:
        """Test session manager respects custom timeout."""
        session_manager = SessionManager(session_timeout_minutes=30)
        self.assertEqual(session_manager._session_timeout, 30)


if __name__ == "__main__":
    unittest.main()
