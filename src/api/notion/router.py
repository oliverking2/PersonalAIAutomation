"""Notion API endpoints for managing databases, data sources, pages, and tasks."""

import logging

from fastapi import APIRouter

from src.api.notion.databases.endpoints import router as databases_router
from src.api.notion.datasources.endpoints import router as datasources_router
from src.api.notion.pages.endpoints import router as pages_router
from src.api.notion.tasks.endpoints import router as tasks_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notion")

router.include_router(databases_router)
router.include_router(datasources_router)
router.include_router(pages_router)
router.include_router(tasks_router)
