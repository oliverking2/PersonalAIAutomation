"""Pydantic models for Telegram integration."""

from typing import Any

from pydantic import BaseModel, Field


class InlineKeyboardButton(BaseModel):
    """A button in an inline keyboard."""

    text: str
    callback_data: str | None = None
    url: str | None = None


class InlineKeyboardMarkup(BaseModel):
    """Inline keyboard markup for messages."""

    inline_keyboard: list[list[InlineKeyboardButton]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for Telegram API.

        Only includes non-None fields as Telegram rejects null values.
        """
        return {
            "inline_keyboard": [
                [self._button_to_dict(btn) for btn in row] for row in self.inline_keyboard
            ]
        }

    @staticmethod
    def _button_to_dict(btn: InlineKeyboardButton) -> dict[str, str]:
        """Convert a button to dict, excluding None values."""
        result: dict[str, str] = {"text": btn.text}
        if btn.callback_data is not None:
            result["callback_data"] = btn.callback_data
        if btn.url is not None:
            result["url"] = btn.url
        return result


class TelegramUser(BaseModel):
    """Telegram user information."""

    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    """Telegram chat information."""

    id: int
    type: str
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramEntity(BaseModel):
    """Telegram message entity (formatting, links, etc.)."""

    type: str
    offset: int
    length: int
    url: str | None = None


class TelegramMessageInfo(BaseModel):
    """Telegram message information from the API."""

    message_id: int
    date: int
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None
    entities: list[TelegramEntity] | None = None
    reply_to_message: "TelegramMessageInfo | None" = None

    model_config = {"populate_by_name": True}

    def get_text_with_urls(self) -> str | None:
        """Get message text with text_link entities replaced by their URLs.

        For text_link entities (where visible text differs from URL),
        replaces the visible text with the full URL so the agent can
        extract the actual link.

        :returns: Text with URLs resolved, or None if no text.
        """
        if not self.text:
            return None

        if not self.entities:
            return self.text

        # Process entities in reverse order to preserve offsets
        result = self.text
        text_links = sorted(
            [e for e in self.entities if e.type == "text_link" and e.url],
            key=lambda e: e.offset,
            reverse=True,
        )

        for entity in text_links:
            if entity.url:  # Redundant check for type narrowing
                start = entity.offset
                end = entity.offset + entity.length
                result = result[:start] + entity.url + result[end:]

        return result


class CallbackQuery(BaseModel):
    """Telegram callback query from inline keyboard button press."""

    id: str
    from_user: TelegramUser | None = Field(default=None, alias="from")
    message: TelegramMessageInfo | None = None
    chat_instance: str | None = None
    data: str | None = None

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    """Telegram update from getUpdates API."""

    update_id: int
    message: TelegramMessageInfo | None = None
    callback_query: CallbackQuery | None = None


class SendMessageResult(BaseModel):
    """Result of sending a message via Telegram."""

    message_id: int
    chat_id: int
