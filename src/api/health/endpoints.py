"""Health check endpoints."""

import logging

from fastapi import APIRouter

from src.api.health.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Check service health",
    description="Returns the health status of the API service.",
)
def health_check() -> HealthResponse:
    """Check if the API service is healthy.

    :returns: Health status response.
    """
    logger.debug("Health check requested")
    return HealthResponse(status="healthy", version="0.1.0")
