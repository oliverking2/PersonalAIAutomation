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


def get_data_source_id() -> str:
    """Get the configured data source ID from environment."""
    data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID")
    if not data_source_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="NOTION_DATA_SOURCE_ID not configured",
        )
    return data_source_id
