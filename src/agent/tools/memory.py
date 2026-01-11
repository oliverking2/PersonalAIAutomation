"""Memory tools for the AI agent.

System tools that are always available for memory management.
These tools call the memory API endpoints directly.
"""

import logging
from http import HTTPStatus
from typing import Any, cast

from pydantic import BaseModel, Field

from src.agent.enums import MemoryCategory, RiskLevel
from src.agent.models import ToolDef
from src.api.client import InternalAPIClient, InternalAPIClientError

logger = logging.getLogger(__name__)


class AddToMemoryArgs(BaseModel):
    """Arguments for adding to memory."""

    content: str = Field(
        ...,
        description="The fact or information to remember",
        min_length=5,
        max_length=500,
    )
    category: MemoryCategory = Field(
        ...,
        description="Category of memory: person, preference, context, or project",
    )
    subject: str | None = Field(
        None,
        description="Optional subject/entity this memory relates to (e.g., person name, project name)",
        max_length=200,
    )


class UpdateMemoryArgs(BaseModel):
    """Arguments for updating an existing memory."""

    memory_id: str = Field(
        ...,
        description="8-character ID of the memory to update",
    )
    content: str = Field(
        ...,
        description="The updated content for this memory",
        min_length=5,
        max_length=500,
    )
    subject: str | None = Field(
        None,
        description="Optional new subject/entity if the subject itself has changed (e.g., when the boss changes from 'Alec' to 'Sarah')",
        max_length=200,
    )


def _get_client() -> InternalAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return InternalAPIClient()


def _add_to_memory_handler(args: BaseModel) -> dict[str, Any]:
    """Handle add_to_memory tool call.

    :param args: AddToMemoryArgs instance.
    :returns: Created memory details.
    """
    add_args = cast(AddToMemoryArgs, args)

    logger.info(
        f"Add to memory: category={add_args.category}, "
        f"subject={add_args.subject}, content={add_args.content[:50]}..."
    )

    try:
        with _get_client() as client:
            response = cast(
                dict[str, Any],
                client.post(
                    "/memory",
                    json=args.model_dump(mode="json", exclude_none=True),
                ),
            )

        logger.info(f"Memory created: id={response['id']}")

        return {
            "id": response["id"],
            "content": response["content"],
            "category": response["category"],
            "subject": response.get("subject"),
            "created": True,
        }

    except InternalAPIClientError as e:
        if e.status_code == HTTPStatus.CONFLICT:
            # Duplicate subject - existing memory
            return {
                "created": False,
                "error": "duplicate_subject",
                "message": str(e),
            }
        raise


def _update_memory_handler(args: BaseModel) -> dict[str, Any]:
    """Handle update_memory tool call.

    :param args: UpdateMemoryArgs instance.
    :returns: Updated memory details.
    """
    update_args = cast(UpdateMemoryArgs, args)

    logger.info(f"Update memory: id={update_args.memory_id}, content={update_args.content[:50]}...")

    try:
        # Build request body, including subject only if provided
        request_body: dict[str, Any] = {"content": update_args.content}
        if update_args.subject is not None:
            request_body["subject"] = update_args.subject

        with _get_client() as client:
            response = client.patch(
                f"/memory/{update_args.memory_id}",
                json=request_body,
            )

        logger.info(f"Memory updated: id={response['id']}, version={response['version']}")

        return {
            "id": response["id"],
            "content": response["content"],
            "version": response["version"],
            "updated": True,
        }

    except InternalAPIClientError as e:
        if e.status_code == HTTPStatus.NOT_FOUND:
            return {
                "updated": False,
                "error": "not_found",
                "message": f"Memory not found: {update_args.memory_id}",
            }
        if e.status_code == HTTPStatus.BAD_REQUEST:
            return {
                "updated": False,
                "error": "bad_request",
                "message": str(e),
            }
        raise


# Tool definitions
ADD_TO_MEMORY_TOOL = ToolDef(
    name="add_to_memory",
    description=(
        "Store important information for future conversations. Use this when the user "
        "shares facts about people, expresses preferences, or provides context that would "
        "be useful to remember. Ask for confirmation before storing new information."
    ),
    args_model=AddToMemoryArgs,
    handler=_add_to_memory_handler,
    risk_level=RiskLevel.SAFE,
    tags=frozenset({"system", "memory"}),
)

UPDATE_MEMORY_TOOL = ToolDef(
    name="update_memory",
    description=(
        "Update an existing memory when information has changed. Use this instead of "
        "creating a new memory when correcting outdated information. The memory ID "
        "can be found in the system prompt memory section (e.g., [id:a1b2c3d4]). "
        "If the subject itself has changed (e.g., boss changed from Alec to Sarah), "
        "include the new subject to update the memory's subject field."
    ),
    args_model=UpdateMemoryArgs,
    handler=_update_memory_handler,
    risk_level=RiskLevel.SAFE,
    tags=frozenset({"system", "memory"}),
)


def get_memory_tools() -> list[ToolDef]:
    """Get all memory tool definitions.

    :returns: List of ToolDef instances for memory operations.
    """
    return [ADD_TO_MEMORY_TOOL, UPDATE_MEMORY_TOOL]
