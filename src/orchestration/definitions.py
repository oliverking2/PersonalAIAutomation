"""Combine all dagster definitions."""

from dagster import Definitions, EnvVar

from src.orchestration.alerts.definitions import defs as alerts_defs
from src.orchestration.newsletters.definitions import defs as newsletters_defs
from src.orchestration.reminders.definitions import defs as reminders_defs
from src.orchestration.resources import TelegramResource
from src.orchestration.utils.sensors import util_sensor_defs

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

defs = Definitions.merge(newsletters_defs, alerts_defs, reminders_defs, util_sensor_defs)
