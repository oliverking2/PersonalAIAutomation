"""Pydantic models for Telegram integration."""

from pydantic import BaseModel, Field


class SendResult(BaseModel):
    """Result of sending newsletter alerts via Telegram."""

    newsletters_sent: int = 0
    errors: list[str] = Field(default_factory=list)
