"""Combine all dagster definitions."""

from dagster import Definitions, EnvVar
from src.dagster.newsletters.definitions import defs as newsletters_defs
from src.dagster.resources import TelegramResource

core_defs = Definitions(
    resources={
        "telegram": TelegramResource(
            bot_token=EnvVar("TELEGRAM_BOT_TOKEN"),
            chat_id=EnvVar("TELEGRAM_CHAT_ID"),
        ),
        "telegram_errors": TelegramResource(
            bot_token=EnvVar("TELEGRAM_ERROR_BOT_TOKEN"),
            chat_id=EnvVar("TELEGRAM_CHAT_ID"),
        ),
    },
)

defs = Definitions.merge(newsletters_defs)
