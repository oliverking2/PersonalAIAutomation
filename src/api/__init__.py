"""API module for Personal AI Automation."""

from src.api.app import app
from src.api.client import InternalAPIClient, InternalAPIClientError

__all__ = ["InternalAPIClient", "InternalAPIClientError", "app"]
