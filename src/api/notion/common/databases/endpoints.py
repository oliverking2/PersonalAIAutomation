"""Notion API endpoints for managing databases."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.databases.models import (
    DatabaseResponse,
)
from src.api.notion.dependencies import get_notion_client
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/databases", tags=["Notion - Databases"])


@router.get(
    "/{database_id}",
    response_model=DatabaseResponse,
    summary="Retrieve database",
)
def get_database(
    database_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> DatabaseResponse:
    """Retrieve database structure and properties."""
    start = time.perf_counter()
    logger.info(f"Get database: id={database_id}")
    try:
        data = client.get_database(database_id)
        title_items = data.get("title", [])
        title = "".join(item.get("plain_text", "") for item in title_items)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Get database complete: id={database_id}, title={title!r}, "
            f"properties={len(data.get('properties', {}))}, elapsed={elapsed_ms:.0f}ms"
        )

        return DatabaseResponse(
            id=data["id"],
            title=title,
            properties=data.get("properties", {}),
        )
    except NotionClientError as e:
        logger.exception(f"Failed to get database: id={database_id}, error={e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
