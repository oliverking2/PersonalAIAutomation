"""FastAPI application configuration."""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.health import router as health_router
from src.api.tasks import router as tasks_router
from src.api.tasks.models import ErrorResponse
from src.utils.logging import configure_logging

load_dotenv()
configure_logging()

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    :returns: Configured FastAPI application instance.
    """
    application = FastAPI(
        title="Personal AI Automation API",
        description="REST API for triggering newsletter processing and alerting tasks.",
        version="0.1.0",
        responses={
            401: {"model": ErrorResponse, "description": "Unauthorised"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )

    # Register routers
    application.include_router(health_router)
    application.include_router(tasks_router)

    logger.info("FastAPI application created")

    return application


# Application instance for uvicorn
app = create_app()
