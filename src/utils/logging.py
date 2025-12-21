"""Logging configuration for the application."""

import logging
import os
import sys
from collections.abc import Iterable

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_level(level: str) -> int:
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    return numeric_level


def _set_logger_levels(names: Iterable[str], level: int) -> None:
    for name in names:
        logging.getLogger(name).setLevel(level)


def configure_logging() -> None:
    """Configure application-wide logging to stdout only.

    Env vars:
      - LOG_LEVEL: DEBUG/INFO/WARNING/ERROR/CRITICAL (default INFO)
      - LOG_UVICORN_ACCESS: true/false (default false)
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO")
    level = _parse_level(level_name)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Hard reset: ensure exactly one stdout handler with your formatter.
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(handler)

    # Ensure libs don't attach their own handlers; they should propagate to root.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery"):
        lib_logger = logging.getLogger(name)
        lib_logger.handlers.clear()
        lib_logger.propagate = True

    access_enabled = os.environ.get("LOG_UVICORN_ACCESS", "false").strip().lower() == "true"
    if not access_enabled:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _set_logger_levels(("urllib3", "httpx"), level=max(level, logging.INFO))

    logging.getLogger(__name__).info("Logging configured: level=%s", level_name.upper())
