"""Configuration for Telegram integration using pydantic-settings."""

from enum import StrEnum
from functools import cached_property, lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.paths import PROJECT_ROOT

_ENV_FILE = PROJECT_ROOT / ".env"


class TelegramMode(StrEnum):
    """Telegram transport mode."""

    POLLING = "polling"
    WEBHOOK = "webhook"


class TelegramConfig(BaseSettings):
    """Configuration for Telegram integration.

    All settings are loaded from environment variables with the TELEGRAM_ prefix.

    :param bot_token: Telegram bot token from @BotFather.
    :param chat_id: Default chat ID for sending messages (used by alerts).
    :param mode: Transport mode (polling or webhook).
    :param poll_timeout: Timeout in seconds for long polling.
    :param session_timeout_minutes: Minutes of inactivity before session expires.
    :param error_retry_delay: Delay in seconds between retries after an error.
    :param max_consecutive_errors: Maximum consecutive errors before backing off.
    :param backoff_delay: Delay in seconds after max consecutive errors.
    :param allowed_chat_ids: Comma-separated list of chat IDs allowed to interact.
    :param error_bot_token: Separate bot token for error notifications (optional).
    :param error_chat_id: Chat ID for error notifications (optional).
    """

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = Field(..., description="Bot token from @BotFather")
    chat_id: str | None = Field(
        default=None,
        description="Default chat ID for sending messages",
    )
    mode: TelegramMode = Field(
        default=TelegramMode.POLLING,
        description="Transport mode (polling or webhook)",
    )
    poll_timeout: int = Field(
        default=30,
        ge=1,
        le=60,
        description="Long polling timeout in seconds",
    )
    session_timeout_minutes: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Session inactivity timeout in minutes",
    )
    error_retry_delay: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Delay in seconds between retries after an error",
    )
    max_consecutive_errors: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum consecutive errors before backing off",
    )
    backoff_delay: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Delay in seconds after max consecutive errors",
    )
    allowed_chat_ids: str = Field(
        ...,
        description="Comma-separated list of allowed chat IDs",
    )
    error_bot_token: str | None = Field(
        default=None,
        description="Separate bot token for error notifications",
    )
    error_chat_id: str | None = Field(
        default=None,
        description="Chat ID for error notifications",
    )

    @field_validator("allowed_chat_ids")
    @classmethod
    def validate_allowed_chat_ids(cls, v: str) -> str:
        """Validate that at least one chat ID is provided.

        :param v: Raw comma-separated string from environment.
        :returns: The validated string.
        :raises ValueError: If the value is empty or contains no valid IDs.
        """
        chat_ids = [chat_id.strip() for chat_id in v.split(",") if chat_id.strip()]
        if not chat_ids:
            raise ValueError(
                "At least one chat ID must be configured. "
                "Set TELEGRAM_ALLOWED_CHAT_IDS environment variable."
            )
        return v

    @cached_property
    def allowed_chat_ids_set(self) -> frozenset[str]:
        """Get the allowed chat IDs as a frozenset.

        :returns: Frozenset of allowed chat ID strings.
        """
        return frozenset(
            chat_id.strip() for chat_id in self.allowed_chat_ids.split(",") if chat_id.strip()
        )


@lru_cache
def get_telegram_settings() -> TelegramConfig:
    """Get cached Telegram settings.

    Settings are loaded once and cached for the lifetime of the process.

    :returns: Configured TelegramSettings instance.
    """
    return TelegramConfig()  # type: ignore[call-arg]
