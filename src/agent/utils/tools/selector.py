"""Tool selector for the AI agent module."""

import json
import logging

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import CallType, RiskLevel
from src.agent.exceptions import BedrockClientError, ToolSelectionError
from src.agent.models import ToolMetadata, ToolSelectionResult
from src.agent.utils.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Default maximum number of tools to select
DEFAULT_MAX_TOOLS = 5

# Minimum word length for keyword matching in fallback selection
MIN_KEYWORD_LENGTH = 3

# Number of retries for AI selection before falling back
DEFAULT_MAX_RETRIES = 3

TOOL_SELECTION_SYSTEM_PROMPT = """You are a tool selector. Given a user request and a list of available tools, select the most relevant tools that should be exposed to handle the request.

Rules:
1. Select only tools that are directly relevant to the user's intent
2. Prefer SAFE tools over SENSITIVE tools unless the user clearly wants to modify data
3. Order tools by relevance (most relevant first)
4. Select at most {max_tools} tools
5. If no tools are relevant, return an empty list

Available tools:
{tool_descriptions}

Respond with valid JSON only, no other text:
{{
  "tool_names": ["tool1", "tool2"],
  "reasoning": "Brief explanation of why these tools were selected"
}}

"""

ADDITIVE_SELECTION_SYSTEM_PROMPT = """You are a tool selector. The user is continuing a conversation where these tools are already selected: {current_tools}

Determine if the user's message requires ADDITIONAL tools not already selected.

Rules:
1. If the current tools are sufficient for this message, return an empty list
2. Only add tools if the user is asking for something the current tools cannot handle
3. Clarification messages (providing details, dates, confirmations) usually don't need new tools
4. Select at most {max_tools} additional tools

Available tools (excluding already selected):
{tool_descriptions}

Respond with valid JSON only, no other text:
{{
  "tool_names": [],
  "reasoning": "Current tools are sufficient for this clarification"
}}

or if new tools are needed:
{{
  "tool_names": ["new_tool"],
  "reasoning": "User is now asking to do X which requires new_tool"
}}

"""


class ToolSelector:
    """AI-first tool selector using Bedrock Converse.

    Determines which subset of tools should be exposed for a given user request.
    Uses an LLM to analyse intent and select relevant tools.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        client: BedrockClient | None = None,
        max_tools: int = DEFAULT_MAX_TOOLS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Initialise the tool selector.

        :param registry: Tool registry containing available tools.
        :param client: Bedrock client for LLM calls. Creates one if not provided.
        :param max_tools: Maximum number of tools to select per request.
        :param max_retries: Number of retries for AI selection before falling back.
        """
        self.registry = registry
        self.client = client or BedrockClient()
        self.max_tools = max_tools
        self.max_retries = max_retries

    def _format_tool_metadata(self, metadata: list[ToolMetadata]) -> str:
        """Format tool metadata for the LLM prompt.

        :param metadata: List of tool metadata.
        :returns: Formatted string describing available tools.
        """
        lines: list[str] = []
        for tool in metadata:
            tags_str = ", ".join(sorted(tool.tags)) if tool.tags else "none"
            lines.append(
                f"- {tool.name}: {tool.description} [tags: {tags_str}, risk: {tool.risk_level}]"
            )
        return "\n".join(lines)

    def _parse_selection_response(
        self, response_text: str, available_tools: set[str]
    ) -> ToolSelectionResult:
        """Parse the LLM response into a selection result.

        :param response_text: Raw text response from the LLM.
        :param available_tools: Set of valid tool names.
        :returns: Parsed tool selection result.
        :raises ToolSelectionError: If the response cannot be parsed.
        """
        try:
            # Extract JSON from markdown code blocks if present
            text = BedrockClient.extract_json_from_markdown(response_text)

            data = json.loads(text)

            tool_names = data.get("tool_names", [])
            reasoning = data.get("reasoning", "")

            # Filter to only valid tools and respect max limit
            valid_tools = [name for name in tool_names if name in available_tools][: self.max_tools]

            return ToolSelectionResult(
                tool_names=valid_tools,
                reasoning=reasoning,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                f"Failed to parse tool selection response: {e}, response={response_text[:200]}"
            )
            raise ToolSelectionError(f"Failed to parse tool selection response: {e}") from e

    def select(
        self,
        user_intent: str,
        model: str | None = None,
        current_tools: list[str] | None = None,
    ) -> ToolSelectionResult:
        """Select tools for a user request using AI.

        Standard tools (tagged with 'standard') are excluded from selection
        as they are always included in agent runs.

        When current_tools is provided, uses additive mode: only returns tools
        that should be ADDED to the existing set. This is more efficient for
        follow-up messages where the user is providing clarifications.

        :param user_intent: The user's request or intent text.
        :param model: Optional model ID/alias override for selection (e.g., 'haiku').
        :param current_tools: Tools already selected in this conversation. When
            provided, selector returns only additional tools needed.
        :returns: Tool selection result with ordered tool names.
        :raises ToolSelectionError: If selection fails.
        """
        # Only select from non-standard tools (standard tools are always included)
        metadata = self.registry.list_selectable_metadata()

        if not metadata:
            logger.debug("No tools registered, returning empty selection")
            return ToolSelectionResult(
                tool_names=[],
                reasoning="No tools available in registry",
            )

        # In additive mode, exclude already-selected tools from candidates
        current_tools_set = set(current_tools) if current_tools else set()
        if current_tools:
            metadata = [m for m in metadata if m.name not in current_tools_set]
            if not metadata:
                logger.debug("All tools already selected, no additional tools needed")
                return ToolSelectionResult(
                    tool_names=[],
                    reasoning="All relevant tools already selected",
                )

        available_tools = {m.name for m in metadata}
        tool_descriptions = self._format_tool_metadata(metadata)

        # Use appropriate prompt based on mode
        if current_tools:
            system_prompt = ADDITIVE_SELECTION_SYSTEM_PROMPT.format(
                current_tools=current_tools,
                max_tools=self.max_tools,
                tool_descriptions=tool_descriptions,
            )
        else:
            system_prompt = TOOL_SELECTION_SYSTEM_PROMPT.format(
                max_tools=self.max_tools,
                tool_descriptions=tool_descriptions,
            )

        user_message = f"User message: {user_intent}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                # model parameter is required - use 'haiku' as default for cost-effective selection
                effective_model = model or "haiku"
                response = self.client.converse(
                    messages=[self.client.create_user_message(user_message)],
                    model_id=effective_model,
                    system_prompt=system_prompt,
                    max_tokens=512,
                    temperature=0.0,
                    call_type=CallType.SELECTOR,
                    cache_system_prompt=True,
                )

                response_text = self.client.parse_text_response(response)
                result = self._parse_selection_response(response_text, available_tools)

                if current_tools:
                    if result.tool_names:
                        logger.info(
                            f"Additive selection: adding {result.tool_names} to {current_tools}"
                        )
                    else:
                        logger.info(
                            f"Additive selection: no new tools needed, keeping {current_tools}"
                        )
                else:
                    logger.info(
                        f"Tool selection completed: intent='{user_intent[:50]}...', "
                        f"selected={result.tool_names}"
                    )

                return result

            except (BedrockClientError, ToolSelectionError) as e:
                last_error = e
                logger.warning(
                    f"AI tool selection attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

        logger.warning(
            f"AI tool selection failed after {self.max_retries} attempts, falling back: {last_error}"
        )
        return self._fallback_selection(user_intent, metadata)

    def _fallback_selection(
        self, user_intent: str, metadata: list[ToolMetadata]
    ) -> ToolSelectionResult:
        """Tag-based fallback selection when AI selection fails.

        :param user_intent: The user's request text.
        :param metadata: Available tool metadata.
        :returns: Tool selection based on keyword matching.
        """
        intent_lower = user_intent.lower()
        scored_tools: list[tuple[str, int]] = []

        # Score tools based on keyword matches
        for tool in metadata:
            score = 0

            # Check if tool name words appear in intent
            name_words = tool.name.replace("_", " ").split()
            for word in name_words:
                if word.lower() in intent_lower:
                    score += 2

            # Check if description words appear in intent
            desc_words = tool.description.lower().split()
            for word in desc_words:
                if len(word) > MIN_KEYWORD_LENGTH and word in intent_lower:
                    score += 1

            # Check tag matches
            for tag in tool.tags:
                if tag.lower() in intent_lower:
                    score += 3

            # Prefer safe tools
            if tool.risk_level == RiskLevel.SAFE:
                score += 1

            if score > 0:
                scored_tools.append((tool.name, score))

        # Sort by score descending and take top N
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        selected = [name for name, _ in scored_tools[: self.max_tools]]

        logger.info(f"Fallback tool selection: intent='{user_intent[:50]}...', selected={selected}")

        return ToolSelectionResult(
            tool_names=selected,
            reasoning="Selected via fallback keyword matching",
        )

    def select_by_tags(self, tags: set[str]) -> ToolSelectionResult:
        """Select tools by tag without AI.

        Useful for deterministic tool selection based on known categories.

        :param tags: Tags to filter by.
        :returns: Tool selection result.
        """
        tools = self.registry.filter_by_tags(tags)

        # Sort by risk level (safe first), then name
        sorted_tools = sorted(
            tools,
            key=lambda t: (t.risk_level != RiskLevel.SAFE, t.name),
        )

        selected = [t.name for t in sorted_tools[: self.max_tools]]

        return ToolSelectionResult(
            tool_names=selected,
            reasoning=f"Selected by tags: {', '.join(sorted(tags))}",
        )
