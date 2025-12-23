"""FastAPI application configuration."""

import logging

from fastapi import Depends, FastAPI

from src.api.health import router as health_router
from src.api.models import ErrorResponse
from src.api.notion import router as notion_router
from src.api.security import verify_token
from src.observability.sentry import init_sentry
from src.utils.logging import configure_logging

configure_logging()
init_sentry()

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    :returns: Configured FastAPI application instance.
    """
    application = FastAPI(
        title="Personal AI Automation API",
        version="1.0.0",
        responses={
            401: {"model": ErrorResponse, "description": "Unauthorised"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )

    # Register routers
    application.include_router(health_router)
    application.include_router(notion_router, dependencies=[Depends(verify_token)])

    logger.info("FastAPI application created")

    return application


# Application instance for uvicorn
app = create_app()
