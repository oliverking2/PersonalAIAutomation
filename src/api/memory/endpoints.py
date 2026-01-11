"""API endpoints for agent memory management."""

import logging
import time

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import NoResultFound

from src.agent.enums import MemoryCategory
from src.api.memory.models import (
    CreateMemoryRequest,
    MemoryListResponse,
    MemoryResponse,
    MemoryVersionResponse,
    MemoryWithHistoryResponse,
    UpdateMemoryRequest,
)
from src.database.connection import get_session
from src.database.memory import (
    AgentMemory,
    create_memory,
    delete_memory,
    find_memory_by_subject,
    get_active_memories,
    get_memory_with_versions,
    update_memory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


def _memory_to_response(memory: AgentMemory) -> MemoryResponse:
    """Convert a memory model to response.

    :param memory: The database model.
    :returns: API response model.
    """
    current_version = memory.current_version

    return MemoryResponse(
        id=memory.id,
        category=MemoryCategory(memory.category),
        subject=memory.subject,
        content=memory.current_content or "",
        version=current_version.version_number if current_version else 0,
        created_at=memory.created_at,
        updated_at=current_version.created_at if current_version else None,
    )


@router.get(
    "",
    response_model=MemoryListResponse,
    summary="List active memories",
)
def list_memories() -> MemoryListResponse:
    """List all active memories.

    Returns all non-deleted memories ordered by category and creation time.
    This ordering is consistent for prompt caching.
    """
    start = time.perf_counter()

    logger.info("List memories")

    with get_session() as session:
        memories = get_active_memories(session)
        results = [_memory_to_response(m) for m in memories]

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"List memories complete: count={len(results)}, elapsed={elapsed_ms:.0f}ms")

    return MemoryListResponse(memories=results, total=len(results))


@router.get(
    "/{memory_id}",
    response_model=MemoryWithHistoryResponse,
    summary="Get memory with history",
)
def get_memory(memory_id: str) -> MemoryWithHistoryResponse:
    """Get a specific memory with its full version history.

    :param memory_id: The 8-character memory ID.
    :returns: Memory with all versions.
    :raises HTTPException: If memory not found.
    """
    start = time.perf_counter()

    logger.info(f"Get memory: id={memory_id}")

    with get_session() as session:
        try:
            memory = get_memory_with_versions(session, memory_id)
        except NoResultFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory not found: {memory_id}",
            )

        versions = [
            MemoryVersionResponse(
                version_number=v.version_number,
                content=v.content,
                created_at=v.created_at,
                source_conversation_id=str(v.source_conversation_id)
                if v.source_conversation_id
                else None,
            )
            for v in memory.versions
        ]

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Get memory complete: id={memory_id}, versions={len(versions)}, elapsed={elapsed_ms:.0f}ms"
    )

    return MemoryWithHistoryResponse(
        id=memory.id,
        category=MemoryCategory(memory.category),
        subject=memory.subject,
        created_at=memory.created_at,
        versions=versions,
    )


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create memory",
)
def create_memory_endpoint(request: CreateMemoryRequest) -> MemoryResponse:
    """Create a new memory.

    If a memory with the same subject already exists, returns a 409 Conflict
    with a suggestion to use update instead.

    :param request: Memory creation request.
    :returns: The created memory.
    :raises HTTPException: If memory with same subject exists.
    """
    start = time.perf_counter()

    logger.info(
        f"Create memory: category={request.category}, subject={request.subject}, "
        f"content={request.content[:50]!r}..."
    )

    with get_session() as session:
        # Check for existing memory with same subject
        if request.subject:
            existing = find_memory_by_subject(session, request.subject)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Memory with subject '{request.subject}' already exists (id: {existing.id}). "
                    f"Use PATCH /memory/{existing.id} to update it.",
                )

        memory = create_memory(
            session=session,
            content=request.content,
            category=request.category,
            subject=request.subject,
        )

        response = _memory_to_response(memory)

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Create memory complete: id={response.id}, elapsed={elapsed_ms:.0f}ms")

    return response


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Update memory",
)
def update_memory_endpoint(memory_id: str, request: UpdateMemoryRequest) -> MemoryResponse:
    """Update an existing memory.

    Creates a new version of the memory with the updated content. The memory ID
    remains the same.

    :param memory_id: The 8-character memory ID.
    :param request: Memory update request.
    :returns: The updated memory.
    :raises HTTPException: If memory not found or is deleted.
    """
    start = time.perf_counter()

    logger.info(f"Update memory: id={memory_id}, content={request.content[:50]!r}...")

    with get_session() as session:
        try:
            memory = update_memory(
                session=session,
                memory_id=memory_id,
                content=request.content,
                subject=request.subject,
            )
        except NoResultFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory not found: {memory_id}",
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        response = _memory_to_response(memory)

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Update memory complete: id={memory_id}, version={response.version}, elapsed={elapsed_ms:.0f}ms"
    )

    return response


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete memory",
)
def delete_memory_endpoint(memory_id: str) -> None:
    """Soft-delete a memory.

    Sets the deleted_at timestamp. The memory and its versions remain in the
    database but won't appear in active memory lists.

    :param memory_id: The 8-character memory ID.
    :raises HTTPException: If memory not found.
    """
    start = time.perf_counter()

    logger.info(f"Delete memory: id={memory_id}")

    with get_session() as session:
        try:
            delete_memory(session, memory_id)
        except NoResultFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory not found: {memory_id}",
            )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Delete memory complete: id={memory_id}, elapsed={elapsed_ms:.0f}ms")
