"""Shared dependencies for API endpoints."""

import logging
import os

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer()


def get_api_token() -> str:
    """Retrieve the API authentication token from environment.

    :returns: The configured API token.
    :raises ValueError: If API_AUTH_TOKEN is not set.
    """
    token = os.environ.get("API_AUTH_TOKEN")
    if not token:
        raise ValueError(
            "API authentication token not configured. Set API_AUTH_TOKEN environment variable."
        )
    return token


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Verify the Bearer token from request headers.

    :param credentials: The HTTP Authorisation credentials.
    :returns: The validated token.
    :raises HTTPException: If token is invalid or missing.
    """
    try:
        expected_token = get_api_token()
    except ValueError as e:
        logger.error(f"API token configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication not configured",
        ) from e

    if credentials.credentials != expected_token:
        logger.warning("Invalid API token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
