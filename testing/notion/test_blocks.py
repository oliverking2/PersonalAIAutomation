"""Tests for the Notion blocks module."""

import unittest

from src.notion.blocks import (
    blocks_to_markdown,
    markdown_to_blocks,
)


class TestMarkdownToBlocks(unittest.TestCase):
    """Tests for markdown_to_blocks function."""

    def test_empty_markdown_returns_empty_list(self) -> None:
        """Empty string should return empty list."""
        result = markdown_to_blocks("")
        self.assertEqual(result, [])

    def test_whitespace_only_returns_empty_list(self) -> None:
        """Whitespace-only string should return empty list."""
        result = markdown_to_blocks("   \n\n  ")
        self.assertEqual(result, [])

    def test_heading_2(self) -> None:
        """## prefix should create heading_2 block."""
        result = markdown_to_blocks("## Section Title")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "heading_2")
        self.assertEqual(
            result[0]["heading_2"]["rich_text"][0]["text"]["content"],
            "Section Title",
        )

    def test_heading_3(self) -> None:
        """### prefix should create heading_3 block."""
        result = markdown_to_blocks("### Sub-Section")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "heading_3")
        self.assertEqual(
            result[0]["heading_3"]["rich_text"][0]["text"]["content"],
            "Sub-Section",
        )

    def test_unchecked_todo(self) -> None:
        """- [ ] prefix should create unchecked to_do block."""
        result = markdown_to_blocks("- [ ] Buy groceries")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "to_do")
        self.assertEqual(
            result[0]["to_do"]["rich_text"][0]["text"]["content"],
            "Buy groceries",
        )
        self.assertFalse(result[0]["to_do"]["checked"])

    def test_checked_todo_lowercase(self) -> None:
        """- [x] prefix should create checked to_do block."""
        result = markdown_to_blocks("- [x] Complete task")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "to_do")
        self.assertTrue(result[0]["to_do"]["checked"])

    def test_checked_todo_uppercase(self) -> None:
        """- [X] prefix should also create checked to_do block."""
        result = markdown_to_blocks("- [X] Complete task")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "to_do")
        self.assertTrue(result[0]["to_do"]["checked"])

    def test_bulleted_list_item(self) -> None:
        """- prefix (not todo) should create bulleted_list_item block."""
        result = markdown_to_blocks("- First item")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "bulleted_list_item")
        self.assertEqual(
            result[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"],
            "First item",
        )

    def test_numbered_list_item(self) -> None:
        """1. prefix should create numbered_list_item block."""
        result = markdown_to_blocks("1. First item")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "numbered_list_item")
        self.assertEqual(
            result[0]["numbered_list_item"]["rich_text"][0]["text"]["content"],
            "First item",
        )

    def test_numbered_list_various_numbers(self) -> None:
        """Various numbered prefixes should all create numbered_list_item."""
        for prefix in ["1.", "2.", "10.", "99."]:
            with self.subTest(prefix=prefix):
                result = markdown_to_blocks(f"{prefix} Item")
                self.assertEqual(result[0]["type"], "numbered_list_item")

    def test_divider(self) -> None:
        """--- should create divider block."""
        result = markdown_to_blocks("---")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "divider")
        self.assertEqual(result[0]["divider"], {})

    def test_paragraph(self) -> None:
        """Plain text should create paragraph block."""
        result = markdown_to_blocks("This is plain text.")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "paragraph")
        self.assertEqual(
            result[0]["paragraph"]["rich_text"][0]["text"]["content"],
            "This is plain text.",
        )

    def test_multiple_lines(self) -> None:
        """Multiple lines should create multiple blocks."""
        markdown = """## Description
This is the description.

- Item one
- [ ] Task one"""
        result = markdown_to_blocks(markdown)
        # Empty line is skipped
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["type"], "heading_2")
        self.assertEqual(result[1]["type"], "paragraph")
        self.assertEqual(result[2]["type"], "bulleted_list_item")
        self.assertEqual(result[3]["type"], "to_do")

    def test_empty_lines_are_skipped(self) -> None:
        """Empty lines should not create blocks."""
        markdown = "Line one\n\nLine two"
        result = markdown_to_blocks(markdown)
        self.assertEqual(len(result), 2)


class TestBlocksToMarkdown(unittest.TestCase):
    """Tests for blocks_to_markdown function."""

    def test_empty_blocks_returns_empty_string(self) -> None:
        """Empty list should return empty string."""
        result = blocks_to_markdown([])
        self.assertEqual(result, "")

    def test_heading_2_block(self) -> None:
        """heading_2 block should convert to ## prefix."""
        blocks = [
            {
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"plain_text": "Section Title"}],
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "## Section Title")

    def test_heading_3_block(self) -> None:
        """heading_3 block should convert to ### prefix."""
        blocks = [
            {
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"plain_text": "Sub-Section"}],
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "### Sub-Section")

    def test_unchecked_todo_block(self) -> None:
        """Unchecked to_do block should convert to - [ ] prefix."""
        blocks = [
            {
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"plain_text": "Buy groceries"}],
                    "checked": False,
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "- [ ] Buy groceries")

    def test_checked_todo_block(self) -> None:
        """Checked to_do block should convert to - [x] prefix."""
        blocks = [
            {
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"plain_text": "Complete task"}],
                    "checked": True,
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "- [x] Complete task")

    def test_bulleted_list_item_block(self) -> None:
        """bulleted_list_item block should convert to - prefix."""
        blocks = [
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"plain_text": "First item"}],
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "- First item")

    def test_numbered_list_item_block(self) -> None:
        """numbered_list_item block should convert to numbered prefix."""
        blocks = [
            {
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"plain_text": "First item"}],
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "1. First item")

    def test_numbered_list_counter_increments(self) -> None:
        """Consecutive numbered_list_item blocks should increment counter."""
        blocks = [
            {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"plain_text": "First"}]},
            },
            {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"plain_text": "Second"}]},
            },
            {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"plain_text": "Third"}]},
            },
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "1. First\n2. Second\n3. Third")

    def test_numbered_list_counter_resets(self) -> None:
        """Counter should reset when a non-numbered block appears."""
        blocks = [
            {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"plain_text": "First"}]},
            },
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Paragraph"}]},
            },
            {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"plain_text": "New first"}]},
            },
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "1. First\nParagraph\n1. New first")

    def test_divider_block(self) -> None:
        """Divider block should convert to ---."""
        blocks = [{"type": "divider", "divider": {}}]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "---")

    def test_paragraph_block(self) -> None:
        """Paragraph block should convert to plain text."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "This is plain text."}],
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "This is plain text.")

    def test_unknown_block_type_is_skipped(self) -> None:
        """Unknown block types should be skipped."""
        blocks = [
            {"type": "unknown_type", "unknown_type": {}},
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Valid"}]},
            },
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "Valid")

    def test_rich_text_with_text_content(self) -> None:
        """Rich text with text.content structure should be handled."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": "Text content"}}],
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "Text content")


class TestRoundTrip(unittest.TestCase):
    """Tests for round-trip conversion."""

    def test_simple_document_roundtrip(self) -> None:
        """Simple document should survive round-trip conversion."""
        markdown = """## Description
This is a task description.

## Acceptance Criteria
- [ ] First criterion
- [ ] Second criterion

---
Created via AI Agent"""
        blocks = markdown_to_blocks(markdown)
        result = blocks_to_markdown(blocks)
        # Normalise expected (empty lines become nothing)
        expected_lines = [line for line in markdown.split("\n") if line.strip()]
        result_lines = result.split("\n")
        self.assertEqual(result_lines, expected_lines)


class TestMalformedMarkdown(unittest.TestCase):
    """Tests for malformed or edge-case markdown input."""

    def test_heading_without_space_becomes_paragraph(self) -> None:
        """##NoSpace should become a paragraph, not heading."""
        result = markdown_to_blocks("##No space after hashes")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "paragraph")

    def test_heading_with_only_hashes(self) -> None:
        """## alone should become a paragraph."""
        result = markdown_to_blocks("##")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "paragraph")

    def test_heading_with_space_but_no_text(self) -> None:
        """## (with trailing space) should create empty heading."""
        result = markdown_to_blocks("## ")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "heading_2")
        self.assertEqual(
            result[0]["heading_2"]["rich_text"][0]["text"]["content"],
            "",
        )

    def test_todo_without_space_after_bracket(self) -> None:
        """- [x]NoSpace should become bulleted list, not todo."""
        result = markdown_to_blocks("- [x]No space after checkbox")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "bulleted_list_item")

    def test_todo_with_wrong_bracket_format(self) -> None:
        """- [] should become bulleted list."""
        result = markdown_to_blocks("- [] Empty brackets")
        self.assertEqual(result[0]["type"], "bulleted_list_item")

    def test_todo_with_empty_text(self) -> None:
        """- [ ] with no following text should work."""
        result = markdown_to_blocks("- [ ] ")
        self.assertEqual(result[0]["type"], "to_do")
        self.assertEqual(
            result[0]["to_do"]["rich_text"][0]["text"]["content"],
            "",
        )

    def test_numbered_list_without_space(self) -> None:
        """1.NoSpace should become paragraph."""
        result = markdown_to_blocks("1.No space after number")
        self.assertEqual(result[0]["type"], "paragraph")

    def test_numbered_list_with_zero(self) -> None:
        """0. should work as numbered list."""
        result = markdown_to_blocks("0. Zero item")
        self.assertEqual(result[0]["type"], "numbered_list_item")

    def test_bullet_with_only_dash(self) -> None:
        """- alone should become a paragraph (no space after)."""
        result = markdown_to_blocks("-")
        self.assertEqual(result[0]["type"], "paragraph")

    def test_bullet_with_dash_space_only(self) -> None:
        """'- ' with no text should create empty bulleted item."""
        result = markdown_to_blocks("- ")
        self.assertEqual(result[0]["type"], "bulleted_list_item")
        self.assertEqual(
            result[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"],
            "",
        )

    def test_divider_with_extra_dashes(self) -> None:
        """---- should become paragraph, not divider."""
        result = markdown_to_blocks("----")
        self.assertEqual(result[0]["type"], "paragraph")

    def test_divider_with_spaces(self) -> None:
        """'  ---  ' with surrounding spaces should still be divider."""
        result = markdown_to_blocks("  ---  ")
        self.assertEqual(result[0]["type"], "divider")

    def test_unicode_content(self) -> None:
        """Unicode characters should be preserved."""
        result = markdown_to_blocks("## 日本語テスト 🎉")
        self.assertEqual(result[0]["type"], "heading_2")
        self.assertEqual(
            result[0]["heading_2"]["rich_text"][0]["text"]["content"],
            "日本語テスト 🎉",
        )

    def test_very_long_line(self) -> None:
        """Very long lines should be handled."""
        long_text = "A" * 10000
        result = markdown_to_blocks(long_text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "paragraph")
        self.assertEqual(len(result[0]["paragraph"]["rich_text"][0]["text"]["content"]), 10000)

    def test_special_characters(self) -> None:
        """Special characters should be preserved."""
        result = markdown_to_blocks("## <script>alert('xss')</script>")
        content = result[0]["heading_2"]["rich_text"][0]["text"]["content"]
        self.assertEqual(content, "<script>alert('xss')</script>")

    def test_none_input_handled(self) -> None:
        """None-like empty input should return empty list."""
        # The function already handles empty strings; this tests edge cases
        result = markdown_to_blocks("")
        self.assertEqual(result, [])

    def test_newlines_only(self) -> None:
        """Only newlines should return empty list."""
        result = markdown_to_blocks("\n\n\n\n")
        self.assertEqual(result, [])

    def test_tabs_and_spaces(self) -> None:
        """Tabs and spaces should be preserved in content."""
        result = markdown_to_blocks("  \tIndented text")
        self.assertEqual(result[0]["type"], "paragraph")
        self.assertIn("\t", result[0]["paragraph"]["rich_text"][0]["text"]["content"])


class TestMalformedBlocks(unittest.TestCase):
    """Tests for malformed or edge-case block input."""

    def test_missing_type_field(self) -> None:
        """Block without type field should be skipped."""
        blocks = [
            {"no_type": "field"},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Valid"}]}},
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "Valid")

    def test_empty_type_field(self) -> None:
        """Block with empty type should be skipped."""
        blocks = [
            {"type": "", "paragraph": {"rich_text": [{"plain_text": "Ignored"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Valid"}]}},
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "Valid")

    def test_missing_block_content(self) -> None:
        """Block with type but missing content should produce empty text."""
        blocks = [{"type": "paragraph"}]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "")

    def test_missing_rich_text(self) -> None:
        """Block with empty content dict should produce empty text."""
        blocks = [{"type": "paragraph", "paragraph": {}}]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "")

    def test_empty_rich_text_array(self) -> None:
        """Block with empty rich_text array should produce empty text."""
        blocks = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "")

    def test_todo_missing_checked_field(self) -> None:
        """Todo without checked field should default to unchecked."""
        blocks = [
            {
                "type": "to_do",
                "to_do": {"rich_text": [{"plain_text": "Task"}]},
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "- [ ] Task")

    def test_malformed_rich_text_item(self) -> None:
        """Rich text item without plain_text or text.content should be empty."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"other": "field"}]},
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "")

    def test_none_in_blocks_list(self) -> None:
        """None values in blocks list should be handled gracefully."""
        # The function uses .get() which handles missing keys, but let's verify
        # block objects with None values don't crash
        blocks = [
            {"type": "paragraph", "paragraph": None},  # type: ignore[dict-item]
        ]
        # This might raise AttributeError on .get("rich_text", [])
        # Let's verify current behaviour
        try:
            result = blocks_to_markdown(blocks)
            # If it doesn't raise, we get empty string (expected with current impl)
            self.assertEqual(result, "")
        except (AttributeError, TypeError):
            # If it raises, we need to fix the code
            self.fail("blocks_to_markdown should handle None block content gracefully")

    def test_multiple_rich_text_segments(self) -> None:
        """Multiple rich_text segments should be concatenated."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"plain_text": "Hello "},
                        {"plain_text": "World"},
                    ]
                },
            }
        ]
        result = blocks_to_markdown(blocks)
        self.assertEqual(result, "Hello World")


if __name__ == "__main__":
    unittest.main()
