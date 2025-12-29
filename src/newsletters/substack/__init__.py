"""Substack newsletter processing module."""

from src.newsletters.substack.config import SUBSTACK_PUBLICATIONS
from src.newsletters.substack.models import SubstackProcessingResult
from src.newsletters.substack.service import SubstackService

__all__ = [
    "SUBSTACK_PUBLICATIONS",
    "SubstackProcessingResult",
    "SubstackService",
]
