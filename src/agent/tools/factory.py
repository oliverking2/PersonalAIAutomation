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
from typing import Any

from pydantic import BaseModel, Field, create_model

from src.agent.api_client import AgentAPIClient
from src.agent.enums import RiskLevel
from src.agent.models import ToolDef

# Type alias for content builder functions
ContentBuilder = Callable[[BaseModel], str]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CRUDToolConfig:
    """Configuration for generating CRUD tools for a domain.

    :param domain: Singular domain name (e.g., 'task', 'goal').
    :param domain_plural: Plural domain name (e.g., 'tasks', 'goals').
    :param endpoint_prefix: API endpoint prefix (e.g., '/notion/tasks').
    :param id_field: Name of the ID field for get/update (e.g., 'task_id').
    :param query_model: Pydantic model for query arguments.
    :param create_model: Pydantic model for create arguments.
    :param update_model: Pydantic model for update arguments (without ID).
    :param enum_fields: Mapping of field names to enum types for descriptions.
    :param tags: Tags to apply to all tools in this domain.
    :param query_description: Custom query tool description (optional).
    :param get_description: Custom get tool description (optional).
    :param create_description: Custom create tool description (optional).
    :param update_description: Custom update tool description (optional).
    :param content_builder: Function to build content from agent args (optional).
    """

    domain: str
    domain_plural: str
    endpoint_prefix: str
    id_field: str
    query_model: type[BaseModel]
    create_model: type[BaseModel]
    update_model: type[BaseModel] | None = None
    enum_fields: dict[str, type[StrEnum]] = field(default_factory=dict)
    tags: frozenset[str] = field(default_factory=frozenset)
    query_description: str | None = None
    get_description: str | None = None
    create_description: str | None = None
    update_description: str | None = None
    content_builder: ContentBuilder | None = None


def _get_client() -> AgentAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return AgentAPIClient()


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
            response = client.post(
                f"{config.endpoint_prefix}/query",
                json=args.model_dump(mode="json", exclude_none=True),
            )

        items = response.get("results", [])
        return {"items": items, "count": len(items)}

    enum_hints = _format_enum_hints(config.enum_fields)
    description = config.query_description or (
        f"Query {config.domain_plural} from the tracker. "
        f"Use name_filter for fuzzy search by {config.domain} name. "
        f"Response includes fuzzy_match_quality ('good' or 'weak') - "
        f"ask for clarification if 'weak'. {enum_hints}"
    )

    return ToolDef(
        name=f"query_{config.domain_plural}",
        description=description.strip(),
        tags=config.tags | {"query", "list"},
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

    description = config.get_description or (
        f"Get details of a specific {config.domain} by its ID."
    )

    return ToolDef(
        name=f"get_{config.domain}",
        description=description,
        tags=config.tags | {"get", "item"},
        risk_level=RiskLevel.SAFE,
        args_model=get_args_model,
        handler=get_handler,
    )


def _create_create_tool(config: CRUDToolConfig) -> ToolDef:
    """Generate create tool for a domain.

    :param config: Domain configuration.
    :returns: ToolDef for creating a new item.
    """

    def create_handler(args: BaseModel) -> dict[str, Any]:
        logger.debug(f"Creating {config.domain}")

        # Build API payload
        payload = args.model_dump(mode="json", exclude_none=True)

        # If content builder is configured, build content from structured inputs
        if config.content_builder:
            payload["content"] = config.content_builder(args)
            # Remove structured input fields that aren't in the API model
            payload.pop("description", None)
            payload.pop("notes", None)

        with _get_client() as client:
            response = client.post(config.endpoint_prefix, json=payload)

        return {"item": response, "created": True}

    enum_hints = _format_enum_hints(config.enum_fields)
    description = config.create_description or f"Create a new {config.domain}. {enum_hints}"

    return ToolDef(
        name=f"create_{config.domain}",
        description=description.strip(),
        tags=config.tags | {"create", "item"},
        risk_level=RiskLevel.SAFE,
        args_model=config.create_model,
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
            return {"error": "No properties to update", "updated": False}

        with _get_client() as client:
            response = client.patch(f"{config.endpoint_prefix}/{item_id}", json=payload)

        return {"item": response, "updated": True}

    enum_hints = _format_enum_hints(config.enum_fields)
    description = config.update_description or (
        f"Update an existing {config.domain}. Requires the {config.id_field}. {enum_hints}"
    )

    return ToolDef(
        name=f"update_{config.domain}",
        description=description.strip(),
        tags=config.tags | {"update", "item"},
        risk_level=RiskLevel.SENSITIVE,
        args_model=update_args_model,
        handler=update_handler,
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
