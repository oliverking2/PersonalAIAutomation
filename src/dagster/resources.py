"""Resources for Dagster pipelines."""

from pydantic import Field

from dagster import ConfigurableResource
from src.telegram import TelegramClient


class TelegramResource(ConfigurableResource[TelegramClient]):
    """Dagster resource providing a Telegram client."""

    bot_token: str = Field(..., description="Telegram bot token")
    chat_id: str = Field(..., description="Target chat ID")

    def get_client(self) -> TelegramClient:
        """Get a Telegram client instance."""
        return TelegramClient(
            bot_token=self.bot_token,
            chat_id=self.chat_id,
        )

    def send_message(self, text: str) -> bool:
        """Send a text message to the configured chat."""
        return self.get_client().send_message(text)
