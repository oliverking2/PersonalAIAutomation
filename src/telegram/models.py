"""Pydantic models for Telegram integration."""

from pydantic import BaseModel, Field


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


class TelegramUpdate(BaseModel):
    """Telegram update from getUpdates API."""

    update_id: int
    message: TelegramMessageInfo | None = None


class SendMessageResult(BaseModel):
    """Result of sending a message via Telegram."""

    message_id: int
    chat_id: int
