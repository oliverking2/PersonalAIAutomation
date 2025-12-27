"""Pydantic models for Telegram integration."""

from pydantic import BaseModel, Field


class SendResult(BaseModel):
    """Result of sending newsletter alerts via Telegram."""

    newsletters_sent: int = 0
    errors: list[str] = Field(default_factory=list)


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


class TelegramMessageInfo(BaseModel):
    """Telegram message information from the API."""

    message_id: int
    date: int
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    """Telegram update from getUpdates API."""

    update_id: int
    message: TelegramMessageInfo | None = None


class SendMessageResult(BaseModel):
    """Result of sending a message via Telegram."""

    message_id: int
    chat_id: int
