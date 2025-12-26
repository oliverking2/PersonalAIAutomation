"""Markdown to/from Notion blocks conversion.

This module provides functions to convert between markdown text and
Notion block objects, supporting a subset of common block types.
"""

from __future__ import annotations

import re
from typing import Any


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """Convert markdown text to Notion block objects.

    Supports the following markdown patterns:
    - ## Heading -> heading_2
    - ### Heading -> heading_3
    - - [ ] Item -> to_do (unchecked)
    - - [x] Item -> to_do (checked)
    - - Item -> bulleted_list_item
    - 1. Item -> numbered_list_item
    - --- -> divider
    - Plain text -> paragraph

    :param markdown: Markdown formatted text.
    :returns: List of Notion block objects.
    """
    if not markdown or not markdown.strip():
        return []

    blocks: list[dict[str, Any]] = []
    lines = markdown.split("\n")

    for line in lines:
        block = _parse_line_to_block(line)
        if block:
            blocks.append(block)

    return blocks


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Convert Notion blocks to markdown text.

    Supports the following block types:
    - heading_2 -> ## Heading
    - heading_3 -> ### Heading
    - to_do -> - [ ] Item or - [x] Item
    - bulleted_list_item -> - Item
    - numbered_list_item -> 1. Item
    - divider -> ---
    - paragraph -> Plain text

    :param blocks: List of Notion block objects.
    :returns: Markdown formatted text.
    """
    if not blocks:
        return ""

    lines: list[str] = []
    numbered_counter = 1

    for block in blocks:
        block_type = block.get("type", "")
        line = _block_to_line(block, block_type, numbered_counter)
        if line is not None:
            lines.append(line)
            if block_type == "numbered_list_item":
                numbered_counter += 1
            else:
                numbered_counter = 1

    return "\n".join(lines)


def _parse_line_to_block(line: str) -> dict[str, Any] | None:
    """Parse a single markdown line to a Notion block.

    :param line: A single line of markdown text.
    :returns: Notion block object or None for empty lines.
    """
    stripped = line.strip()

    # Empty line - skip
    if not stripped:
        return None

    # Divider
    if stripped == "---":
        return {"type": "divider", "divider": {}}

    # Try pattern-based matches
    block = _try_pattern_match(line)
    if block:
        return block

    # Default: paragraph
    return _create_text_block("paragraph", line)


def _try_pattern_match(line: str) -> dict[str, Any] | None:
    """Try to match line against known markdown patterns.

    :param line: A single line of markdown text.
    :returns: Notion block object or None if no pattern matches.
    """
    # Headings
    if line.startswith("### "):
        return _create_text_block("heading_3", line[4:].strip())
    if line.startswith("## "):
        return _create_text_block("heading_2", line[3:].strip())

    # List items (todo, bulleted)
    if line.startswith("- "):
        return _parse_list_item(line)

    # Numbered list item
    numbered_match = re.match(r"^(\d+)\.\s+(.+)$", line)
    if numbered_match:
        return _create_text_block("numbered_list_item", numbered_match.group(2).strip())

    return None


def _parse_list_item(line: str) -> dict[str, Any]:
    """Parse a list item line (todo or bulleted).

    :param line: A line starting with "- ".
    :returns: Notion block object for the list item.
    """
    # To-do items
    if line.startswith("- [ ] "):
        return _create_todo_block(line[6:].strip(), checked=False)
    if line.startswith("- [x] ") or line.startswith("- [X] "):
        return _create_todo_block(line[6:].strip(), checked=True)

    # Regular bulleted list item
    return _create_text_block("bulleted_list_item", line[2:].strip())


def _create_text_block(block_type: str, text: str) -> dict[str, Any]:
    """Create a Notion block with rich text content.

    :param block_type: The Notion block type.
    :param text: The text content.
    :returns: Notion block object.
    """
    return {
        "type": block_type,
        block_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def _create_todo_block(text: str, *, checked: bool) -> dict[str, Any]:
    """Create a Notion to_do block.

    :param text: The text content.
    :param checked: Whether the todo is checked.
    :returns: Notion to_do block object.
    """
    return {
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "checked": checked,
        },
    }


def _block_to_line(block: dict[str, Any], block_type: str, numbered_counter: int) -> str | None:
    """Convert a single Notion block to a markdown line.

    :param block: The Notion block object.
    :param block_type: The block type.
    :param numbered_counter: Current counter for numbered lists.
    :returns: Markdown line or None.
    """
    if block_type == "divider":
        return "---"

    # Handle to_do specially due to checked state
    if block_type == "to_do":
        to_do = block.get("to_do") or {}
        text = _extract_text(to_do)
        checked = to_do.get("checked", False) if isinstance(to_do, dict) else False
        checkbox = "[x]" if checked else "[ ]"
        return f"- {checkbox} {text}"

    # Handle numbered list specially due to counter
    if block_type == "numbered_list_item":
        text = _extract_text(block.get("numbered_list_item"))
        return f"{numbered_counter}. {text}"

    # Handle simple prefix-based blocks
    prefix_map = {
        "heading_2": "## ",
        "heading_3": "### ",
        "bulleted_list_item": "- ",
        "paragraph": "",
    }

    if block_type in prefix_map:
        text = _extract_text(block.get(block_type))
        return f"{prefix_map[block_type]}{text}"

    # Unknown block type - skip
    return None


def _extract_text(block_content: dict[str, Any] | None) -> str:
    """Extract plain text from Notion rich text array.

    :param block_content: The block content containing rich_text, or None.
    :returns: Plain text string.
    """
    if block_content is None:
        return ""
    rich_text = block_content.get("rich_text", [])
    if not isinstance(rich_text, list):
        return ""
    return "".join(
        item.get("plain_text", item.get("text", {}).get("content", ""))
        for item in rich_text
        if isinstance(item, dict)
    )
