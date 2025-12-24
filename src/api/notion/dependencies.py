"""Notion API dependencies."""

import logging
import os

from fastapi import HTTPException, status

from src.notion.client import NotionClient

logger = logging.getLogger(__name__)


def get_notion_client() -> NotionClient:
    """Create a NotionClient instance."""
    try:
        return NotionClient()
    except ValueError as e:
        logger.error(f"Failed to initialise Notion client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notion integration not configured",
        ) from e


def _get_env_or_error(var_name: str) -> str:
    """Get environment variable or raise HTTP 500 error.

    :param var_name: Name of the environment variable to retrieve.
    :returns: The value of the environment variable.
    :raises HTTPException: If the variable is not set.
    """
    value = os.environ.get(var_name)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{var_name} not configured",
        )
    return value


def get_task_data_source_id() -> str:
    """Get the configured task data source ID from environment."""
    return _get_env_or_error("NOTION_TASK_DATA_SOURCE_ID")


def get_goals_data_source_id() -> str:
    """Get the configured goals data source ID from environment."""
    return _get_env_or_error("NOTION_GOALS_DATA_SOURCE_ID")


def get_reading_data_source_id() -> str:
    """Get the configured reading list data source ID from environment."""
    return _get_env_or_error("NOTION_READING_LIST_DATA_SOURCE_ID")
