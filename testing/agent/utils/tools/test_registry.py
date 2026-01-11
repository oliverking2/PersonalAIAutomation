"""Tests for ToolRegistry."""

import unittest
from typing import Any

from pydantic import BaseModel

from src.agent.enums import RiskLevel
from src.agent.exceptions import DomainSizeError, DuplicateToolError, ToolNotFoundError
from src.agent.models import ToolDef
from src.agent.utils.tools.registry import ToolRegistry, create_default_registry


class DummyArgs(BaseModel):
    """Dummy argument model for testing."""

    value: str


def dummy_handler(args: DummyArgs) -> dict[str, Any]:
    """Return dummy data for testing."""
    return {"value": args.value}


class TestToolRegistry(unittest.TestCase):
    """Tests for ToolRegistry."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.registry = ToolRegistry()
        self.tool = ToolDef(
            name="test_tool",
            description="A test tool",
            tags=frozenset({"test"}),
            risk_level=RiskLevel.SAFE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )

    def test_register_tool(self) -> None:
        """Test registering a tool."""
        self.registry.register(self.tool)

        self.assertIn("test_tool", self.registry)
        self.assertEqual(len(self.registry), 1)

    def test_register_duplicate_raises_error(self) -> None:
        """Test that registering a duplicate tool raises an error."""
        self.registry.register(self.tool)

        with self.assertRaises(DuplicateToolError) as ctx:
            self.registry.register(self.tool)

        self.assertEqual(ctx.exception.tool_name, "test_tool")

    def test_get_tool(self) -> None:
        """Test retrieving a tool by name."""
        self.registry.register(self.tool)

        retrieved = self.registry.get("test_tool")

        self.assertEqual(retrieved.name, "test_tool")

    def test_get_missing_tool_raises_error(self) -> None:
        """Test that getting a missing tool raises an error."""
        with self.assertRaises(ToolNotFoundError) as ctx:
            self.registry.get("nonexistent")

        self.assertEqual(ctx.exception.tool_name, "nonexistent")

    def test_get_many(self) -> None:
        """Test retrieving multiple tools."""
        tool2 = ToolDef(
            name="tool2",
            description="Another tool",
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(tool2)

        tools = self.registry.get_many(["test_tool", "tool2"])

        self.assertEqual(len(tools), 2)
        self.assertEqual(tools[0].name, "test_tool")
        self.assertEqual(tools[1].name, "tool2")

    def test_list_all(self) -> None:
        """Test listing all tools."""
        self.registry.register(self.tool)

        all_tools = self.registry.list_all()

        self.assertEqual(len(all_tools), 1)
        self.assertEqual(all_tools[0].name, "test_tool")

    def test_list_metadata(self) -> None:
        """Test listing tool metadata."""
        self.registry.register(self.tool)

        metadata = self.registry.list_metadata()

        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].name, "test_tool")
        self.assertEqual(metadata[0].description, "A test tool")
        self.assertEqual(metadata[0].tags, frozenset({"test"}))
        self.assertEqual(metadata[0].risk_level, RiskLevel.SAFE)

    def test_filter_by_tags(self) -> None:
        """Test filtering tools by tags."""
        tool2 = ToolDef(
            name="tool2",
            description="Another tool",
            tags=frozenset({"other"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(tool2)

        filtered = self.registry.filter_by_tags({"test"})

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].name, "test_tool")

    def test_filter_by_risk_level(self) -> None:
        """Test filtering tools by risk level."""
        sensitive_tool = ToolDef(
            name="sensitive",
            description="Sensitive tool",
            risk_level=RiskLevel.SENSITIVE,
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(sensitive_tool)

        safe_tools = self.registry.filter_by_risk_level(RiskLevel.SAFE)
        sensitive_tools = self.registry.filter_by_risk_level(RiskLevel.SENSITIVE)

        self.assertEqual(len(safe_tools), 1)
        self.assertEqual(safe_tools[0].name, "test_tool")
        self.assertEqual(len(sensitive_tools), 1)
        self.assertEqual(sensitive_tools[0].name, "sensitive")

    def test_to_bedrock_tool_config(self) -> None:
        """Test generating Bedrock tool config."""
        self.registry.register(self.tool)

        config = self.registry.to_bedrock_tool_config(["test_tool"])

        self.assertIn("tools", config)
        self.assertEqual(len(config["tools"]), 1)
        self.assertIn("toolSpec", config["tools"][0])

    def test_to_bedrock_tool_config_with_cache_points(self) -> None:
        """Test generating Bedrock tool config with cache points per domain."""
        # Register tools in two domains
        tool_a1 = ToolDef(
            name="tool_a1",
            description="Domain A tool 1",
            tags=frozenset({"domain:a"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool_a2 = ToolDef(
            name="tool_a2",
            description="Domain A tool 2",
            tags=frozenset({"domain:a"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool_b1 = ToolDef(
            name="tool_b1",
            description="Domain B tool 1",
            tags=frozenset({"domain:b"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(tool_a1)
        self.registry.register(tool_a2)
        self.registry.register(tool_b1)

        config = self.registry.to_bedrock_tool_config_with_cache_points(["domain:a", "domain:b"])

        tools_list = config["tools"]
        # Should have: tool_a1, tool_a2, cachePoint, tool_b1, cachePoint
        self.assertEqual(len(tools_list), 5)

        # First two should be toolSpecs for domain A
        self.assertIn("toolSpec", tools_list[0])
        self.assertIn("toolSpec", tools_list[1])

        # Third should be cachePoint
        self.assertIn("cachePoint", tools_list[2])
        self.assertEqual(tools_list[2]["cachePoint"]["type"], "default")

        # Fourth should be toolSpec for domain B
        self.assertIn("toolSpec", tools_list[3])

        # Fifth should be cachePoint
        self.assertIn("cachePoint", tools_list[4])

    def test_to_bedrock_tool_config_with_cache_points_preserves_order(self) -> None:
        """Test that domain order is preserved for cache stability."""
        tool_a = ToolDef(
            name="tool_a",
            description="Domain A",
            tags=frozenset({"domain:a"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool_b = ToolDef(
            name="tool_b",
            description="Domain B",
            tags=frozenset({"domain:b"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(tool_a)
        self.registry.register(tool_b)

        # Order A, B
        config_ab = self.registry.to_bedrock_tool_config_with_cache_points(["domain:a", "domain:b"])
        # Order B, A
        config_ba = self.registry.to_bedrock_tool_config_with_cache_points(["domain:b", "domain:a"])

        # First tool in each config should match the first domain
        self.assertEqual(config_ab["tools"][0]["toolSpec"]["name"], "tool_a")
        self.assertEqual(config_ba["tools"][0]["toolSpec"]["name"], "tool_b")

    def test_contains(self) -> None:
        """Test the __contains__ method."""
        self.registry.register(self.tool)

        self.assertTrue("test_tool" in self.registry)
        self.assertFalse("other" in self.registry)

    def test_len(self) -> None:
        """Test the __len__ method."""
        self.assertEqual(len(self.registry), 0)

        self.registry.register(self.tool)
        self.assertEqual(len(self.registry), 1)

    def test_get_standard_tools_empty(self) -> None:
        """Test get_standard_tools returns empty when no standard tools."""
        self.registry.register(self.tool)  # Not tagged as standard

        standard = self.registry.get_standard_tools()

        self.assertEqual(len(standard), 0)

    def test_get_standard_tools(self) -> None:
        """Test get_standard_tools returns tools tagged with 'standard'."""
        standard_tool = ToolDef(
            name="standard_tool",
            description="A standard tool",
            tags=frozenset({"standard", "utility"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)  # Not standard
        self.registry.register(standard_tool)

        standard = self.registry.get_standard_tools()

        self.assertEqual(len(standard), 1)
        self.assertEqual(standard[0].name, "standard_tool")

    def test_get_selectable_tools(self) -> None:
        """Test get_selectable_tools excludes standard tools."""
        standard_tool = ToolDef(
            name="standard_tool",
            description="A standard tool",
            tags=frozenset({"standard"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)  # Selectable
        self.registry.register(standard_tool)  # Not selectable

        selectable = self.registry.get_selectable_tools()

        self.assertEqual(len(selectable), 1)
        self.assertEqual(selectable[0].name, "test_tool")

    def test_list_selectable_metadata(self) -> None:
        """Test list_selectable_metadata excludes standard tools."""
        standard_tool = ToolDef(
            name="standard_tool",
            description="A standard tool",
            tags=frozenset({"standard"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(self.tool)
        self.registry.register(standard_tool)

        metadata = self.registry.list_selectable_metadata()

        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].name, "test_tool")

    def test_get_domains_empty(self) -> None:
        """Test get_domains returns empty set when no domain tags."""
        self.registry.register(self.tool)  # Has tags but no domain: prefix

        domains = self.registry.get_domains()

        self.assertEqual(domains, set())

    def test_get_domains(self) -> None:
        """Test get_domains returns all unique domain tags."""
        tool1 = ToolDef(
            name="tool1",
            description="Tool 1",
            tags=frozenset({"domain:tasks", "query"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool2 = ToolDef(
            name="tool2",
            description="Tool 2",
            tags=frozenset({"domain:tasks", "create"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool3 = ToolDef(
            name="tool3",
            description="Tool 3",
            tags=frozenset({"domain:goals", "query"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(tool1)
        self.registry.register(tool2)
        self.registry.register(tool3)

        domains = self.registry.get_domains()

        self.assertEqual(domains, {"domain:tasks", "domain:goals"})

    def test_get_tools_by_domain(self) -> None:
        """Test get_tools_by_domain returns all tools for a domain."""
        tool1 = ToolDef(
            name="query_tasks",
            description="Query tasks",
            tags=frozenset({"domain:tasks", "query"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool2 = ToolDef(
            name="create_tasks",
            description="Create tasks",
            tags=frozenset({"domain:tasks", "create"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool3 = ToolDef(
            name="query_goals",
            description="Query goals",
            tags=frozenset({"domain:goals", "query"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(tool1)
        self.registry.register(tool2)
        self.registry.register(tool3)

        tasks_tools = self.registry.get_tools_by_domain("domain:tasks")
        goals_tools = self.registry.get_tools_by_domain("domain:goals")

        self.assertEqual(len(tasks_tools), 2)
        self.assertEqual(len(goals_tools), 1)
        task_names = {t.name for t in tasks_tools}
        self.assertEqual(task_names, {"query_tasks", "create_tasks"})

    def test_get_tools_by_domain_empty(self) -> None:
        """Test get_tools_by_domain returns empty list for unknown domain."""
        self.registry.register(self.tool)

        tools = self.registry.get_tools_by_domain("domain:nonexistent")

        self.assertEqual(tools, [])

    def test_get_domain_tool_count(self) -> None:
        """Test get_domain_tool_count returns accurate counts."""
        tool1 = ToolDef(
            name="tool1",
            description="Tool 1",
            tags=frozenset({"domain:tasks"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool2 = ToolDef(
            name="tool2",
            description="Tool 2",
            tags=frozenset({"domain:tasks"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        tool3 = ToolDef(
            name="tool3",
            description="Tool 3",
            tags=frozenset({"domain:goals"}),
            args_model=DummyArgs,
            handler=dummy_handler,
        )
        self.registry.register(tool1)
        self.registry.register(tool2)
        self.registry.register(tool3)

        counts = self.registry.get_domain_tool_count()

        self.assertEqual(counts, {"domain:tasks": 2, "domain:goals": 1})

    def test_get_domain_tool_count_empty(self) -> None:
        """Test get_domain_tool_count returns empty dict for no domains."""
        self.registry.register(self.tool)  # No domain tag

        counts = self.registry.get_domain_tool_count()

        self.assertEqual(counts, {})

    def test_validate_domain_sizes_passes_for_small_domains(self) -> None:
        """Test validate_domain_sizes passes when domains are under limit."""
        for i in range(4):
            self.registry.register(
                ToolDef(
                    name=f"tool_{i}",
                    description=f"Tool {i}",
                    tags=frozenset({"domain:test"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        # Should not raise
        self.registry.validate_domain_sizes(max_tools=10)

    def test_validate_domain_sizes_raises_for_large_domain(self) -> None:
        """Test validate_domain_sizes raises when a domain exceeds limit."""
        for i in range(11):
            self.registry.register(
                ToolDef(
                    name=f"tool_{i}",
                    description=f"Tool {i}",
                    tags=frozenset({"domain:test"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        with self.assertRaises(DomainSizeError) as ctx:
            self.registry.validate_domain_sizes(max_tools=10)

        self.assertEqual(ctx.exception.domain, "domain:test")
        self.assertEqual(ctx.exception.tool_count, 11)
        self.assertEqual(ctx.exception.max_tools, 10)

    def test_validate_domain_sizes_with_custom_limit(self) -> None:
        """Test validate_domain_sizes respects custom max_tools limit."""
        for i in range(5):
            self.registry.register(
                ToolDef(
                    name=f"tool_{i}",
                    description=f"Tool {i}",
                    tags=frozenset({"domain:test"}),
                    args_model=DummyArgs,
                    handler=dummy_handler,
                )
            )

        # Should pass with limit of 5
        self.registry.validate_domain_sizes(max_tools=5)

        # Add one more tool
        self.registry.register(
            ToolDef(
                name="tool_5",
                description="Tool 5",
                tags=frozenset({"domain:test"}),
                args_model=DummyArgs,
                handler=dummy_handler,
            )
        )

        # Should fail with limit of 5
        with self.assertRaises(DomainSizeError):
            self.registry.validate_domain_sizes(max_tools=5)


class TestCreateDefaultRegistry(unittest.TestCase):
    """Tests for create_default_registry function."""

    def test_creates_registry_with_all_tools(self) -> None:
        """Test that create_default_registry creates a populated registry."""
        registry = create_default_registry()

        # Should have 20 tools: 4 reading + 4 goals + 4 tasks + 4 ideas + 4 reminders
        self.assertEqual(len(registry), 20)

    def test_contains_reading_list_tools(self) -> None:
        """Test that registry contains reading list tools."""
        registry = create_default_registry()

        self.assertIn("query_reading_list", registry)
        self.assertIn("get_reading_item", registry)
        self.assertIn("create_reading_list", registry)
        self.assertIn("update_reading_item", registry)

    def test_contains_goals_tools(self) -> None:
        """Test that registry contains goals tools."""
        registry = create_default_registry()

        self.assertIn("query_goals", registry)
        self.assertIn("get_goal", registry)
        self.assertIn("create_goals", registry)
        self.assertIn("update_goal", registry)

    def test_contains_tasks_tools(self) -> None:
        """Test that registry contains tasks tools."""
        registry = create_default_registry()

        self.assertIn("query_tasks", registry)
        self.assertIn("get_task", registry)
        self.assertIn("create_tasks", registry)
        self.assertIn("update_task", registry)

    def test_contains_ideas_tools(self) -> None:
        """Test that registry contains ideas tools."""
        registry = create_default_registry()

        self.assertIn("query_ideas", registry)
        self.assertIn("get_idea", registry)
        self.assertIn("create_ideas", registry)
        self.assertIn("update_idea", registry)

    def test_contains_reminders_tools(self) -> None:
        """Test that registry contains reminders tools."""
        registry = create_default_registry()

        self.assertIn("create_reminder", registry)
        self.assertIn("query_reminders", registry)
        self.assertIn("update_reminder", registry)
        self.assertIn("cancel_reminder", registry)

    def test_tools_can_be_retrieved(self) -> None:
        """Test that tools can be retrieved from the registry."""
        registry = create_default_registry()

        tool = registry.get("query_reading_list")

        self.assertEqual(tool.name, "query_reading_list")
        self.assertEqual(tool.risk_level, RiskLevel.SAFE)

    def test_can_filter_by_tags(self) -> None:
        """Test filtering tools by domain-specific tags."""
        registry = create_default_registry()

        reading_tools = registry.filter_by_tags({"reading"})
        goals_tools = registry.filter_by_tags({"goals"})
        tasks_tools = registry.filter_by_tags({"tasks"})
        ideas_tools = registry.filter_by_tags({"ideas"})
        reminders_tools = registry.filter_by_tags({"reminders"})

        self.assertEqual(len(reading_tools), 4)
        self.assertEqual(len(goals_tools), 4)
        self.assertEqual(len(tasks_tools), 4)
        self.assertEqual(len(ideas_tools), 4)
        self.assertEqual(len(reminders_tools), 4)

    def test_contains_domain_tags(self) -> None:
        """Test that all tools have domain tags."""
        registry = create_default_registry()

        domains = registry.get_domains()

        # Should have all expected domains
        self.assertIn("domain:reading_list", domains)
        self.assertIn("domain:goals", domains)
        self.assertIn("domain:tasks", domains)
        self.assertIn("domain:ideas", domains)
        self.assertIn("domain:reminders", domains)

    def test_get_tools_by_domain_returns_all_domain_tools(self) -> None:
        """Test that get_tools_by_domain returns all tools for each domain."""
        registry = create_default_registry()

        reading_tools = registry.get_tools_by_domain("domain:reading_list")
        goals_tools = registry.get_tools_by_domain("domain:goals")
        tasks_tools = registry.get_tools_by_domain("domain:tasks")
        ideas_tools = registry.get_tools_by_domain("domain:ideas")
        reminders_tools = registry.get_tools_by_domain("domain:reminders")

        self.assertEqual(len(reading_tools), 4)
        self.assertEqual(len(goals_tools), 4)
        self.assertEqual(len(tasks_tools), 4)
        self.assertEqual(len(ideas_tools), 4)
        self.assertEqual(len(reminders_tools), 4)

    def test_all_domains_under_max_tools_limit(self) -> None:
        """Test that all domains in default registry are under max tool limit."""
        registry = create_default_registry()
        counts = registry.get_domain_tool_count()

        for domain, count in counts.items():
            self.assertLessEqual(
                count,
                10,
                f"Domain {domain} has {count} tools, exceeds max of 10",
            )


if __name__ == "__main__":
    unittest.main()
