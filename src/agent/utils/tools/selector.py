"""Tool selector for the AI agent module."""

import json
import logging

from src.agent.bedrock_client import BedrockClient
from src.agent.enums import CallType
from src.agent.exceptions import BedrockClientError, ToolSelectionError
from src.agent.models import ToolSelectionResult
from src.agent.utils.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Default maximum number of tools to select
DEFAULT_MAX_TOOLS = 10

# Default maximum number of domains
DEFAULT_MAX_DOMAINS = 3

# Number of retries for AI selection before falling back
DEFAULT_MAX_RETRIES = 3

# System prompts are fully static for prompt caching - dynamic content goes in user message
DOMAIN_SELECTION_SYSTEM_PROMPT = f"""You are a domain selector. Given a user request, identify which domains are relevant.

A domain is a category of tools (e.g., tasks, goals, reminders). When you select a domain, ALL tools for that domain become available.

The user message contains:
1. The available domains and their tools
2. The user's request

Rules:
1. Select domains where the user might need ANY operation (query, create, update, delete)
2. A conversation about "tasks" should select the entire "tasks" domain
3. Select at most {DEFAULT_MAX_DOMAINS} domains
4. Order by relevance (most relevant first)
5. If no domains are relevant, return an empty list

Respond with valid JSON only, no other text:
{{{{
  "domains": ["domain:tasks", "domain:goals"],
  "reasoning": "User wants to work with tasks and goals"
}}}}"""

ADDITIVE_DOMAIN_SELECTION_PROMPT = f"""You are a domain selector for continuing conversations.

The user message contains:
1. The currently selected domains
2. The available domains (excluding already selected)
3. The user's new message

Determine if the user's message requires ADDITIONAL domains.

Rules:
1. If the user is still working within the current domains, return an empty list
2. Only add domains if the user explicitly mentions a new topic area
3. Clarification messages (providing details, dates, confirmations) usually don't need new domains
4. Select at most {DEFAULT_MAX_DOMAINS} additional domains

Respond with valid JSON only, no other text:
{{{{
  "domains": [],
  "reasoning": "User is still working with current domains"
}}}}

or if new domains are needed:
{{{{
  "domains": ["domain:reminders"],
  "reasoning": "User is now asking about reminders"
}}}}"""


class ToolSelector:
    """Domain-based tool selector using Bedrock Converse.

    Selects entire domains (e.g., all task tools) rather than individual tools.
    Uses recency-based pruning to manage tool count across conversation turns.
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
        :param max_tools: Maximum number of tools to include.
        :param max_retries: Number of retries for AI selection before falling back.
        """
        self.registry = registry
        self.client = client or BedrockClient()
        self.max_tools = max_tools
        self.max_retries = max_retries

    def _format_domain_descriptions(self, domains: set[str]) -> str:
        """Format domain descriptions for the LLM prompt.

        :param domains: Set of domain tags.
        :returns: Formatted string describing available domains.
        """
        lines: list[str] = []
        for domain in sorted(domains):
            tools = self.registry.get_tools_by_domain(domain)
            tool_names = ", ".join(t.name for t in tools)
            lines.append(f"- {domain}: {len(tools)} tools ({tool_names})")
        return "\n".join(lines)

    def _get_selectable_domains(self) -> set[str]:
        """Get domains from selectable (non-standard) tools.

        :returns: Set of domain tags.
        """
        selectable = self.registry.get_selectable_tools()
        domains: set[str] = set()
        for tool in selectable:
            for tag in tool.tags:
                if tag.startswith("domain:"):
                    domains.add(tag)
        return domains

    def _tools_to_domains(self, tool_names: list[str]) -> list[str]:
        """Extract unique domains from a list of tool names.

        Preserves order based on first occurrence.

        :param tool_names: List of tool names.
        :returns: Ordered list of domain tags.
        """
        domains: list[str] = []
        seen: set[str] = set()
        for name in tool_names:
            if name in self.registry:
                tool = self.registry.get(name)
                for tag in tool.tags:
                    if tag.startswith("domain:") and tag not in seen:
                        domains.append(tag)
                        seen.add(tag)
        return domains

    def _merge_domains_by_recency(
        self,
        intent_domains: list[str],
        existing_domains: list[str],
    ) -> list[str]:
        """Merge domains with existing domains taking priority for cache stability.

        Existing domains are placed first (already cached and should be preserved),
        followed by new intent domains. This ensures that when pruning occurs,
        new domains are dropped rather than existing ones, maximising cache hits.

        :param intent_domains: Domains from current user intent (to be added).
        :param existing_domains: Domains already in conversation (preserved for caching).
        :returns: Merged list with existing domains first.
        """
        # Existing domains first for cache stability, then new domains
        return list(dict.fromkeys(existing_domains + intent_domains))

    def _prune_domains_to_limit(self, domains: list[str]) -> list[str]:
        """Prune domains to stay within tool limit.

        Drops complete domains from the end (oldest/least relevant)
        until the total tool count is under max_tools.

        :param domains: Recency-ordered domain list.
        :returns: Pruned domain list.
        """
        domain_counts = self.registry.get_domain_tool_count()
        result: list[str] = []
        total_tools = 0

        for domain in domains:
            tool_count = domain_counts.get(domain, 0)
            if total_tools + tool_count <= self.max_tools:
                result.append(domain)
                total_tools += tool_count
            else:
                logger.debug(
                    f"Dropping domain {domain} ({tool_count} tools) - "
                    f"would exceed limit of {self.max_tools}"
                )

        if len(result) < len(domains):
            dropped = set(domains) - set(result)
            logger.info(f"Pruned domains due to tool limit: kept={result}, dropped={list(dropped)}")

        return result

    def _expand_domains_to_tools(self, domains: list[str]) -> list[str]:
        """Expand domain tags to individual tool names.

        :param domains: List of domain tags.
        :returns: List of tool names.
        """
        tool_names: list[str] = []
        seen: set[str] = set()
        for domain in domains:
            for tool in self.registry.get_tools_by_domain(domain):
                if tool.name not in seen:
                    tool_names.append(tool.name)
                    seen.add(tool.name)
        return tool_names

    def _parse_domain_response(
        self, response_text: str, available_domains: set[str]
    ) -> tuple[list[str], str]:
        """Parse the LLM response for domain selection.

        :param response_text: Raw text response from the LLM.
        :param available_domains: Set of valid domain tags.
        :returns: Tuple of (domain list, reasoning).
        :raises ToolSelectionError: If the response cannot be parsed.
        """
        try:
            text = BedrockClient.extract_json_from_markdown(response_text)
            data = json.loads(text)

            domains = data.get("domains", [])
            reasoning = data.get("reasoning", "")

            # Filter to valid domains, deduplicate, respect limit
            valid_domains = list(dict.fromkeys(d for d in domains if d in available_domains))[
                :DEFAULT_MAX_DOMAINS
            ]

            return valid_domains, reasoning

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                f"Failed to parse domain selection response: {e}, response={response_text[:200]}"
            )
            raise ToolSelectionError(f"Failed to parse domain selection response: {e}") from e

    def _select_domains(
        self,
        user_intent: str,
        available_domains: set[str],
        current_domains: list[str] | None = None,
        model: str | None = None,
    ) -> tuple[list[str], str]:
        """Select domains using LLM.

        Dynamic content (domain descriptions, current domains) is passed in the user
        message to keep system prompts static for caching.

        :param user_intent: The user's request text.
        :param available_domains: Set of available domain tags.
        :param current_domains: Already selected domains (for additive mode).
        :param model: Optional model override.
        :returns: Tuple of (selected domains, reasoning).
        """
        # Build user message with dynamic content (keeps system prompt static for caching)
        if current_domains:
            available_for_selection = available_domains - set(current_domains)
            if not available_for_selection:
                return [], "All domains already selected"
            domain_descriptions = self._format_domain_descriptions(available_for_selection)
            system_prompt = ADDITIVE_DOMAIN_SELECTION_PROMPT
            user_message = (
                f"Currently selected domains: {', '.join(current_domains)}\n\n"
                f"Available domains:\n{domain_descriptions}\n\n"
                f"User message: {user_intent}"
            )
        else:
            domain_descriptions = self._format_domain_descriptions(available_domains)
            system_prompt = DOMAIN_SELECTION_SYSTEM_PROMPT
            user_message = (
                f"Available domains:\n{domain_descriptions}\n\nUser message: {user_intent}"
            )

        effective_model = model or "haiku"

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
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
                domains, reasoning = self._parse_domain_response(response_text, available_domains)

                return domains, reasoning

            except (BedrockClientError, ToolSelectionError) as e:
                last_error = e
                logger.warning(
                    f"AI domain selection attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

        logger.warning(
            f"AI domain selection failed after {self.max_retries} attempts: {last_error}"
        )
        # Return empty and let caller handle fallback
        return [], "AI selection failed"

    def select(
        self,
        user_intent: str,
        model: str | None = None,
        current_tools: list[str] | None = None,
    ) -> ToolSelectionResult:
        """Select tools using domain-based grouping.

        Instead of selecting individual tools, identifies relevant domains
        and returns ALL tools for those domains. Uses recency-based pruning
        to manage tool count - oldest domains are dropped entirely when
        the limit is exceeded.

        :param user_intent: The user's request or intent text.
        :param model: Optional model ID/alias override for selection.
        :param current_tools: Tools already selected in this conversation.
        :returns: Tool selection result with tool names and domains.
        """
        # Get available domains from selectable tools
        available_domains = self._get_selectable_domains()

        if not available_domains:
            logger.debug("No domains available, returning empty selection")
            return ToolSelectionResult(
                tool_names=[],
                domains=[],
                reasoning="No domains available in registry",
            )

        # Get existing domains from current tools
        existing_domains = self._tools_to_domains(current_tools) if current_tools else []

        # Select domains from current intent
        intent_domains, reasoning = self._select_domains(
            user_intent,
            available_domains,
            existing_domains if existing_domains else None,
            model,
        )

        # If AI selection failed entirely, use fallback
        if not intent_domains and reasoning == "AI selection failed":
            intent_domains, reasoning = self._fallback_domain_selection(
                user_intent, available_domains
            )

        # Merge by recency (intent domains first, then existing)
        merged_domains = self._merge_domains_by_recency(intent_domains, existing_domains)

        # Prune oldest domains if over limit
        pruned_domains = self._prune_domains_to_limit(merged_domains)

        # Expand domains to tools
        tool_names = self._expand_domains_to_tools(pruned_domains)

        logger.info(
            f"Domain selection completed: intent='{user_intent[:50]}...', "
            f"domains={pruned_domains}, tools={len(tool_names)}"
        )

        return ToolSelectionResult(
            tool_names=tool_names,
            domains=pruned_domains,
            reasoning=reasoning,
        )

    def _fallback_domain_selection(
        self, user_intent: str, available_domains: set[str]
    ) -> tuple[list[str], str]:
        """Keyword-based fallback for domain selection.

        Matches domain names against user intent.

        :param user_intent: The user's request text.
        :param available_domains: Available domain tags.
        :returns: Tuple of (matched domains, reasoning).
        """
        intent_lower = user_intent.lower()
        matched: list[str] = []

        for domain in available_domains:
            # Extract domain name (e.g., 'domain:tasks' -> 'tasks')
            domain_name = domain.split(":", 1)[1] if ":" in domain else domain

            # Check if domain name appears in intent
            if (
                domain_name.lower() in intent_lower
                or domain_name.rstrip("s").lower() in intent_lower
            ):
                matched.append(domain)

        # Limit to max domains
        matched = matched[:DEFAULT_MAX_DOMAINS]

        logger.info(f"Fallback domain selection: intent='{user_intent[:50]}...', matched={matched}")

        return matched, "Selected via fallback keyword matching"

    def select_by_tags(self, tags: set[str]) -> ToolSelectionResult:
        """Select tools by tag without AI.

        Useful for deterministic tool selection based on known categories.

        :param tags: Tags to filter by.
        :returns: Tool selection result.
        """
        tools = self.registry.filter_by_tags(tags)
        tool_names = [t.name for t in tools]

        # Extract domains from selected tools
        domains = self._tools_to_domains(tool_names)

        return ToolSelectionResult(
            tool_names=tool_names[: self.max_tools],
            domains=domains,
            reasoning=f"Selected by tags: {', '.join(sorted(tags))}",
        )
