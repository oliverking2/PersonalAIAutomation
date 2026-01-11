"""CRUD tool factory for generating domain-specific tools.

This module provides a factory pattern for generating standardised CRUD
(Create, Read, Update, Query) tools for different domains (tasks, goals,
reading list items, etc.).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, Field, create_model

from src.agent.enums import RiskLevel
from src.agent.models import ToolDef
from src.api.client import InternalAPIClient

# Type alias for content builder functions
ContentBuilder = Callable[[BaseModel], str]

logger = logging.getLogger(__name__)


# Fields to include in LLM responses for each operation type
# Only these fields are returned to reduce context size
DEFAULT_QUERY_FIELDS: frozenset[str] = frozenset({"id", "status", "priority", "due_date"})
DEFAULT_CREATE_FIELDS: frozenset[str] = frozenset({"id", "status"})
DEFAULT_UPDATE_FIELDS: frozenset[str] = frozenset({"id", "status"})
DEFAULT_GET_FIELDS: frozenset[str] = frozenset()  # Empty = return all fields


@dataclass(frozen=True)
class CRUDToolConfig:
    """Configuration for generating CRUD tools for a domain.

    :param domain: Singular domain name (e.g., 'task', 'goal').
    :param domain_plural: Plural domain name (e.g., 'tasks', 'goals').
    :param endpoint_prefix: API endpoint prefix (e.g., '/notion/tasks').
    :param id_field: Name of the ID field for get/update (e.g., 'task_id').
    :param name_field: Name field to always include in responses (e.g., 'task_name').
    :param query_model: Pydantic model for query arguments.
    :param create_model: Pydantic model for create arguments.
    :param update_model: Pydantic model for update arguments (without ID).
    :param enum_fields: Mapping of field names to enum types for descriptions.
    :param tags: Tags to apply to all tools in this domain.
    :param query_description: Description for the query tool.
    :param get_description: Description for the get tool.
    :param create_description: Description for the create tool.
    :param update_description: Description for the update tool.
    :param content_builder: Function to build content from agent args (optional).
    :param query_fields: Fields to include in query responses (plus name_field).
    :param create_fields: Fields to include in create responses (plus name_field).
    :param update_fields: Fields to include in update responses (plus name_field).
    """

    domain: str
    domain_plural: str
    endpoint_prefix: str
    id_field: str
    name_field: str
    query_model: type[BaseModel]
    create_model: type[BaseModel]
    update_model: type[BaseModel]
    query_description: str
    get_description: str
    create_description: str
    update_description: str
    enum_fields: dict[str, type[StrEnum]] = field(default_factory=dict)
    tags: frozenset[str] = field(default_factory=frozenset)
    content_builder: ContentBuilder | None = None
    query_fields: frozenset[str] = DEFAULT_QUERY_FIELDS
    create_fields: frozenset[str] = DEFAULT_CREATE_FIELDS
    update_fields: frozenset[str] = DEFAULT_UPDATE_FIELDS

    @property
    def domain_tag(self) -> str:
        """Get the domain tag for tool grouping.

        Used by the ToolSelector to group all tools in a domain together.

        :returns: Domain tag in format 'domain:{domain_plural}'.
        """
        return f"domain:{self.domain_plural}"


def _get_client() -> InternalAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return InternalAPIClient()


def _filter_response_fields(
    item: dict[str, Any],
    fields: frozenset[str],
    name_field: str,
) -> dict[str, Any]:
    """Filter response to only include specified fields.

    Always includes the name field for LLM context.

    :param item: Full response item from API.
    :param fields: Set of field names to include.
    :param name_field: Name field to always include.
    :returns: Filtered item with only specified fields.
    """
    if not fields:
        return item  # Empty set = return all fields

    include_fields = fields | {name_field}
    return {k: v for k, v in item.items() if k in include_fields}


def _format_enum_hints(enum_fields: dict[str, type[StrEnum]]) -> str:
    """Format enum field values for tool descriptions.

    :param enum_fields: Mapping of field names to enum types.
    :returns: Formatted string of valid values.
    """
    if not enum_fields:
        return ""

    hints = []
    for field_name, enum_class in enum_fields.items():
        values = ", ".join(str(v) for v in enum_class)
        hints.append(f"{field_name} ({values})")

    return "Filter options: " + "; ".join(hints) + "."


def _create_get_args_model(config: CRUDToolConfig) -> type[BaseModel]:
    """Create a Pydantic model for get-by-ID arguments.

    :param config: Domain configuration.
    :returns: Pydantic model class.
    """
    field_def: tuple[type[str], Any] = (
        str,
        Field(..., min_length=1, description=f"The Notion page ID of the {config.domain}"),
    )
    return create_model(
        f"Get{config.domain.title()}Args",
        **{config.id_field: field_def},  # type: ignore[call-overload]
    )


def _create_update_args_model(config: CRUDToolConfig) -> type[BaseModel]:
    """Create a Pydantic model for update arguments (with ID).

    :param config: Domain configuration.
    :returns: Pydantic model class extending the update model with ID field.
    """
    field_def: tuple[type[str], Any] = (
        str,
        Field(..., min_length=1, description="The Notion page ID to update"),
    )
    return create_model(
        f"Update{config.domain.title()}Args",
        __base__=config.update_model,
        **{config.id_field: field_def},  # type: ignore[call-overload]
    )


def _create_query_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate query tool for a domain.

    :param config: Domain configuration.
    :returns: ToolDef for querying items.
    """

    def query_handler(args: BaseModel) -> dict[str, Any]:
        logger.debug(f"Querying {config.domain_plural}")

        with _get_client() as client:
            response = cast(
                dict[str, Any],
                client.post(
                    f"{config.endpoint_prefix}/query",
                    json=args.model_dump(mode="json", exclude_none=True),
                ),
            )

        items = response.get("results", [])
        # Filter response fields for LLM context efficiency
        filtered_items = [
            _filter_response_fields(item, config.query_fields, config.name_field) for item in items
        ]
        return {"items": filtered_items, "count": len(filtered_items)}

    return ToolDef(
        name=f"query_{config.domain_plural}",
        description=config.query_description,
        tags=frozenset({config.domain_tag}) | config.tags | {"query", "list"},
        risk_level=RiskLevel.SAFE,
        args_model=config.query_model,
        handler=query_handler,
    )


def _create_get_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate get-by-ID tool for a domain.

    :param config: Domain configuration.
    :returns: ToolDef for getting a single item by ID.
    """
    get_args_model = _create_get_args_model(config)

    def get_handler(args: BaseModel) -> dict[str, Any]:
        item_id = getattr(args, config.id_field)
        logger.debug(f"Getting {config.domain}: {item_id}")

        with _get_client() as client:
            response = client.get(f"{config.endpoint_prefix}/{item_id}")

        return {"item": response}

    return ToolDef(
        name=f"get_{config.domain}",
        description=config.get_description,
        tags=frozenset({config.domain_tag}) | config.tags | {"get", "item"},
        risk_level=RiskLevel.SAFE,
        args_model=get_args_model,
        handler=get_handler,
    )


def _create_bulk_create_args_model(config: CRUDToolConfig) -> type[BaseModel]:
    """Create a Pydantic model for bulk create arguments.

    Wraps the single-item create model in a list to enable bulk creation.

    :param config: Domain configuration.
    :returns: Pydantic model class with items list.
    """
    return create_model(
        f"Create{config.domain_plural.title()}Args",
        items=(
            list[config.create_model],  # type: ignore[name-defined]
            Field(
                ...,
                min_length=1,
                description=f"List of {config.domain_plural} to create (1 or more items)",
            ),
        ),
    )


def _create_create_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate create tool for a domain.

    Supports bulk creation - the LLM can create multiple items in one call.
    The API handles partial success/failure and returns created items and failures.

    :param config: Domain configuration.
    :returns: ToolDef for creating new items.
    """
    bulk_args_model = _create_bulk_create_args_model(config)

    def create_handler(args: BaseModel) -> dict[str, Any]:
        items_to_create: list[BaseModel] = getattr(args, "items")
        logger.debug(f"Creating {len(items_to_create)} {config.domain_plural}")

        # Build payload for all items
        payloads: list[dict[str, Any]] = []
        for item in items_to_create:
            payload = item.model_dump(mode="json", exclude_none=True)

            # If content builder is configured, build content from structured inputs
            if config.content_builder:
                payload["content"] = config.content_builder(item)
                # Remove structured input fields that aren't in the API model
                payload.pop("description", None)
                payload.pop("notes", None)

            payloads.append(payload)

        # Send all items to API - API handles partial success/failure
        with _get_client() as client:
            response = cast(
                dict[str, Any],
                client.post(config.endpoint_prefix, json=payloads),
            )

        # Filter response fields for LLM context efficiency
        created_items = response.get("created", [])
        filtered_items = [
            _filter_response_fields(item, config.create_fields, config.name_field)
            for item in created_items
        ]

        # Build response with counts and items/failures
        result: dict[str, Any] = {
            "created": len(filtered_items),
            "failed": len(response.get("failed", [])),
        }

        if filtered_items:
            result["items"] = filtered_items
        if response.get("failed"):
            result["failures"] = response["failed"]

        return result

    return ToolDef(
        name=f"create_{config.domain_plural}",
        description=config.create_description,
        tags=frozenset({config.domain_tag}) | config.tags | {"create", "item"},
        risk_level=RiskLevel.SAFE,
        args_model=bulk_args_model,
        handler=create_handler,
    )


def _create_update_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate update tool for a domain.

    :param config: Domain configuration.
    :returns: ToolDef for updating an existing item.
    """
    update_args_model = _create_update_args_model(config)

    def update_handler(args: BaseModel) -> dict[str, Any]:
        item_id = getattr(args, config.id_field)
        logger.debug(f"Updating {config.domain}: {item_id}")

        # Exclude ID field from payload (it's in the URL)
        payload = args.model_dump(mode="json", exclude_none=True, exclude={config.id_field})

        # If content builder is configured and description/notes provided, build content
        if config.content_builder:
            description = getattr(args, "description", None)
            notes = getattr(args, "notes", None)
            if description is not None or notes is not None:
                payload["content"] = config.content_builder(args)
            # Remove structured input fields that aren't in the API model
            payload.pop("description", None)
            payload.pop("notes", None)

        if not payload:
            return {
                "error": "No properties to update",
                "error_type": "validation",
                "updated": False,
            }

        with _get_client() as client:
            response = client.patch(f"{config.endpoint_prefix}/{item_id}", json=payload)

        # Filter response fields for LLM context efficiency
        filtered_item = _filter_response_fields(response, config.update_fields, config.name_field)
        return {"item": filtered_item, "updated": True}

    return ToolDef(
        name=f"update_{config.domain}",
        description=config.update_description,
        tags=frozenset({config.domain_tag}) | config.tags | {"update", "item"},
        risk_level=RiskLevel.SENSITIVE,
        args_model=update_args_model,
        handler=update_handler,
        id_field=config.id_field,
    )


def create_crud_tools(config: CRUDToolConfig) -> list[ToolDef]:
    """Generate all CRUD tools for a domain.

    Creates query, get, create, and update tools based on the provided
    configuration.

    :param config: Domain configuration.
    :returns: List of four ToolDef instances (query, get, create, update).
    """
    return [
        _create_query_tool(config),
        _create_get_tool(config),
        _create_create_tool(config),
        _create_update_tool(config),
    ]
