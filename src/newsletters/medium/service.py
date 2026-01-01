"""Service layer for processing Medium Daily Digests."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from src.database.medium import MediumDigest, create_digest
from src.newsletters.base.service import BaseNewsletterService
from src.newsletters.medium.fetcher import MEDIUM_SENDER_EMAIL
from src.newsletters.medium.models import ParsedMediumDigest
from src.newsletters.medium.parser import parse_medium_digest

if TYPE_CHECKING:
    from src.database.core import Base
    from src.newsletters.base.models import ParsedArticleBase, ParsedDigestBase


class MediumService(BaseNewsletterService):
    """Service for processing Medium Daily Digests."""

    @property
    def sender_email(self) -> str:
        """The Medium sender email address."""
        return MEDIUM_SENDER_EMAIL

    @property
    def source_name(self) -> str:
        """Human-readable name for logging."""
        return "Medium"

    @property
    def db_model_class(self) -> type[Base]:
        """The SQLAlchemy model class for Medium digests."""
        return MediumDigest

    def _parse_html(self, html: str) -> Sequence[ParsedArticleBase]:
        """Parse the email HTML and extract articles."""
        return parse_medium_digest(html)

    def _create_digest(
        self,
        metadata: dict[str, Any],
        articles: Sequence[ParsedArticleBase],
    ) -> ParsedDigestBase:
        """Create a ParsedMediumDigest from metadata and articles."""
        return ParsedMediumDigest(
            email_id=metadata["email_id"],
            subject=metadata["subject"],
            received_at=metadata["received_at"],
            articles=articles,  # type: ignore[arg-type]
        )

    def _store_digest(self, parsed: ParsedDigestBase) -> tuple[int, int]:
        """Store the parsed digest in the database."""
        _, new_count, dup_count = create_digest(
            self._session,
            parsed,  # type: ignore[arg-type]
        )
        return new_count, dup_count
