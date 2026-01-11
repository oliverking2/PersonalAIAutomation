"""Database operations for agent memory management."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, selectinload

from src.database.memory.models import AgentMemory, AgentMemoryVersion

logger = logging.getLogger(__name__)


def create_memory(
    session: Session,
    content: str,
    category: str,
    subject: str | None = None,
    source_conversation_id: uuid.UUID | None = None,
) -> AgentMemory:
    """Create a new memory with an initial version.

    :param session: Database session.
    :param content: The memory content.
    :param category: Memory category (person, preference, context, project).
    :param subject: Optional subject/entity this memory relates to.
    :param source_conversation_id: Optional source conversation ID.
    :returns: The created memory with its first version.
    """
    memory = AgentMemory(
        category=category,
        subject=subject,
    )
    session.add(memory)
    session.flush()  # Generate the short ID

    # Create the first version
    version = AgentMemoryVersion(
        memory_id=memory.id,
        version_number=1,
        content=content,
        source_conversation_id=source_conversation_id,
    )
    session.add(version)
    session.flush()

    logger.info(f"Created memory: id={memory.id}, category={category}, subject={subject}")

    return memory


def get_memory_by_id(
    session: Session,
    memory_id: str,
) -> AgentMemory:
    """Get a memory by its ID.

    :param session: Database session.
    :param memory_id: The 8-character memory ID.
    :returns: The memory.
    :raises NoResultFound: If memory not found.
    """
    return session.query(AgentMemory).filter(AgentMemory.id == memory_id).one()


def get_memory_with_versions(
    session: Session,
    memory_id: str,
) -> AgentMemory:
    """Get a memory with all its versions eagerly loaded.

    :param session: Database session.
    :param memory_id: The 8-character memory ID.
    :returns: The memory with versions relationship loaded.
    :raises NoResultFound: If memory not found.
    """
    return (
        session.query(AgentMemory)
        .options(selectinload(AgentMemory.versions))
        .filter(AgentMemory.id == memory_id)
        .one()
    )


def get_active_memories(session: Session) -> list[AgentMemory]:
    """Load all active memories with their versions eagerly loaded.

    IMPORTANT: Memories are ordered by category then created_at to ensure
    consistent ordering for prompt caching. If order changes, cache is invalidated.

    :param session: Database session.
    :returns: List of active memories with versions loaded.
    """
    memories = (
        session.query(AgentMemory)
        .options(selectinload(AgentMemory.versions))
        .filter(AgentMemory.deleted_at.is_(None))
        .order_by(AgentMemory.category, AgentMemory.created_at)
        .all()
    )

    logger.debug(f"Loaded {len(memories)} active memories")
    return memories


def update_memory(
    session: Session,
    memory_id: str,
    content: str,
    subject: str | None = None,
    source_conversation_id: uuid.UUID | None = None,
) -> AgentMemory:
    """Update a memory by creating a new version.

    :param session: Database session.
    :param memory_id: The 8-character memory ID.
    :param content: The new content.
    :param subject: Optional new subject (updates memory metadata if provided).
    :param source_conversation_id: Optional source conversation ID.
    :returns: The updated memory with new version.
    :raises NoResultFound: If memory not found.
    """
    memory = get_memory_with_versions(session, memory_id)

    if not memory.is_active:
        msg = f"Cannot update deleted memory: {memory_id}"
        raise ValueError(msg)

    # Update subject if provided
    if subject is not None:
        memory.subject = subject

    # Get the current version number
    current_version_number = memory.current_version.version_number if memory.current_version else 0

    # Create new version
    new_version = AgentMemoryVersion(
        memory_id=memory_id,
        version_number=current_version_number + 1,
        content=content,
        source_conversation_id=source_conversation_id,
    )
    session.add(new_version)
    session.flush()

    logger.info(f"Updated memory: id={memory_id}, new_version={new_version.version_number}")

    return memory


def delete_memory(
    session: Session,
    memory_id: str,
) -> AgentMemory:
    """Soft-delete a memory by setting deleted_at timestamp.

    :param session: Database session.
    :param memory_id: The 8-character memory ID.
    :returns: The deleted memory.
    :raises NoResultFound: If memory not found.
    """
    memory = get_memory_by_id(session, memory_id)

    memory.deleted_at = datetime.now(UTC)
    session.flush()

    logger.info(f"Deleted memory: id={memory_id}")

    return memory


def find_memory_by_subject(
    session: Session,
    subject: str,
) -> AgentMemory | None:
    """Find an active memory by subject for duplicate detection.

    :param session: Database session.
    :param subject: The subject to search for.
    :returns: The memory if found, None otherwise.
    """
    try:
        return (
            session.query(AgentMemory)
            .filter(
                AgentMemory.subject == subject,
                AgentMemory.deleted_at.is_(None),
            )
            .one()
        )
    except NoResultFound:
        return None
