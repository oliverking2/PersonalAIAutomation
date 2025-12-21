"""Logging configuration for the application."""

import logging
import os
import sys
from pathlib import Path

from src.paths import PROJECT_ROOT

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Configure application-wide logging with file and stdout handlers.

    Reads configuration from environment variables:
        - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO.
        - LOG_FILE: Path to the log file. If relative, uses project root as base.
            Defaults to 'app.log' in the project root.
    """
    level = os.environ.get("LOG_LEVEL", "INFO")
    log_file_env = os.environ.get("LOG_FILE", "app.log")
    log_path = Path(log_file_env)

    # Use project root for relative paths
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path

    # Validate log level
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    # Create formatter
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(numeric_level)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    # File handler
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logging.info("Logging configured: level=%s, file=%s", level.upper(), log_path)
