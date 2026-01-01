"""Base database utilities and repository patterns."""

from src.database.base.repository import (
    compute_url_hash,
    get_unsent_by_alerted_at,
    mark_alerted,
    record_exists_by_field,
)

__all__ = [
    "compute_url_hash",
    "get_unsent_by_alerted_at",
    "mark_alerted",
    "record_exists_by_field",
]
