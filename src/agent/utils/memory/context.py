"""Memory context building utilities for the AI agent."""

from collections import defaultdict

from src.database.memory.models import AgentMemory


def build_memory_context(memories: list[AgentMemory]) -> str:
    """Build memory context for the system prompt.

    Creates a formatted section showing all active memories grouped by category.
    Memory IDs are included so the agent can reference them when updating.

    The ordering of memories must be deterministic for prompt caching to work effectively.
    Memories should be pre-sorted by (category, created_at) before being passed to this function.

    :param memories: Active memory entries (pre-sorted by category, created_at).
    :returns: Formatted memory section for the system prompt.
    """
    if not memories:
        return ""

    # Group memories by category
    grouped: dict[str, list[AgentMemory]] = defaultdict(list)
    for mem in memories:
        grouped[mem.category].append(mem)

    # Build formatted output
    lines = ["## Your Memory", ""]
    lines.append(
        "The following is information you've learned about the user from previous conversations."
    )
    lines.append(
        "Use this context naturally. To update a memory, use the update_memory tool with the memory ID."
    )
    lines.append("")

    # Output each category
    for category in sorted(grouped.keys()):  # Sort for consistency
        entries = grouped[category]
        lines.append(f"### {category.title()}")

        for entry in entries:
            # Include short ID for reference in updates
            subject_prefix = f"[{entry.subject}] " if entry.subject else ""
            lines.append(f"- [id:{entry.id}] {subject_prefix}{entry.current_content}")

        lines.append("")

    return "\n".join(lines)
