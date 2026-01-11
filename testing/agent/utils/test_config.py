"""Tests for agent config module."""

import unittest
from decimal import Decimal

from src.agent.utils.config import (
    DEFAULT_AGENT_CONFIG,
    MODEL_PRICING,
    AgentConfig,
    ModelPricing,
)


class TestModelPricing(unittest.TestCase):
    """Tests for ModelPricing NamedTuple."""

    def test_model_pricing_fields(self) -> None:
        """Should have all required pricing fields."""
        pricing = ModelPricing(
            input_per_1k=Decimal("0.001"),
            output_per_1k=Decimal("0.005"),
            cache_read_per_1k=Decimal("0.0001"),
            cache_write_per_1k=Decimal("0.00125"),
        )

        self.assertEqual(pricing.input_per_1k, Decimal("0.001"))
        self.assertEqual(pricing.output_per_1k, Decimal("0.005"))
        self.assertEqual(pricing.cache_read_per_1k, Decimal("0.0001"))
        self.assertEqual(pricing.cache_write_per_1k, Decimal("0.00125"))

    def test_model_pricing_immutable(self) -> None:
        """ModelPricing should be immutable (NamedTuple)."""
        pricing = ModelPricing(
            input_per_1k=Decimal("0.001"),
            output_per_1k=Decimal("0.005"),
            cache_read_per_1k=Decimal("0.0001"),
            cache_write_per_1k=Decimal("0.00125"),
        )

        with self.assertRaises(AttributeError):
            pricing.input_per_1k = Decimal("0.002")  # type: ignore[misc]


class TestModelPricingDict(unittest.TestCase):
    """Tests for MODEL_PRICING dictionary."""

    def test_all_models_defined(self) -> None:
        """Should have pricing for all supported models."""
        expected_models = {"haiku", "sonnet", "opus"}
        self.assertEqual(set(MODEL_PRICING.keys()), expected_models)

    def test_pricing_values_are_positive(self) -> None:
        """All pricing values should be positive."""
        for model, pricing in MODEL_PRICING.items():
            with self.subTest(model=model):
                self.assertGreater(pricing.input_per_1k, Decimal("0"))
                self.assertGreater(pricing.output_per_1k, Decimal("0"))
                self.assertGreater(pricing.cache_read_per_1k, Decimal("0"))
                self.assertGreater(pricing.cache_write_per_1k, Decimal("0"))

    def test_cache_read_cheaper_than_input(self) -> None:
        """Cache read tokens should be cheaper than input tokens."""
        for model, pricing in MODEL_PRICING.items():
            with self.subTest(model=model):
                self.assertLess(pricing.cache_read_per_1k, pricing.input_per_1k)

    def test_cache_write_more_expensive_than_input(self) -> None:
        """Cache write tokens should be more expensive than input tokens (125% premium)."""
        for model, pricing in MODEL_PRICING.items():
            with self.subTest(model=model):
                self.assertGreater(pricing.cache_write_per_1k, pricing.input_per_1k)


class TestAgentConfig(unittest.TestCase):
    """Tests for AgentConfig dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        config = AgentConfig()

        self.assertEqual(config.max_steps, 5)
        self.assertEqual(config.selector_model, "haiku")
        self.assertEqual(config.chat_model, "sonnet")
        self.assertEqual(config.max_tokens, 4096)
        self.assertEqual(config.window_size, 15)
        self.assertEqual(config.batch_threshold, 5)
        self.assertEqual(config.max_classification_retries, 2)

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = AgentConfig(
            max_steps=10,
            selector_model="sonnet",
            chat_model="opus",
            max_tokens=8192,
            window_size=20,
            batch_threshold=10,
            max_classification_retries=5,
        )

        self.assertEqual(config.max_steps, 10)
        self.assertEqual(config.selector_model, "sonnet")
        self.assertEqual(config.chat_model, "opus")
        self.assertEqual(config.max_tokens, 8192)
        self.assertEqual(config.window_size, 20)
        self.assertEqual(config.batch_threshold, 10)
        self.assertEqual(config.max_classification_retries, 5)

    def test_frozen_immutable(self) -> None:
        """AgentConfig should be immutable (frozen dataclass)."""
        config = AgentConfig()

        with self.assertRaises(AttributeError):
            config.max_steps = 10  # type: ignore[misc]

    def test_hashable(self) -> None:
        """Frozen dataclass should be hashable."""
        config = AgentConfig()
        # Should not raise
        hash(config)

    def test_equality(self) -> None:
        """Two configs with same values should be equal."""
        config1 = AgentConfig(max_steps=10)
        config2 = AgentConfig(max_steps=10)

        self.assertEqual(config1, config2)

    def test_inequality(self) -> None:
        """Two configs with different values should not be equal."""
        config1 = AgentConfig(max_steps=10)
        config2 = AgentConfig(max_steps=5)

        self.assertNotEqual(config1, config2)


class TestDefaultAgentConfig(unittest.TestCase):
    """Tests for DEFAULT_AGENT_CONFIG singleton."""

    def test_default_config_exists(self) -> None:
        """DEFAULT_AGENT_CONFIG should be an AgentConfig instance."""
        self.assertIsInstance(DEFAULT_AGENT_CONFIG, AgentConfig)

    def test_default_config_has_expected_values(self) -> None:
        """DEFAULT_AGENT_CONFIG should have standard defaults."""
        self.assertEqual(DEFAULT_AGENT_CONFIG.max_steps, 5)
        self.assertEqual(DEFAULT_AGENT_CONFIG.selector_model, "haiku")
        self.assertEqual(DEFAULT_AGENT_CONFIG.chat_model, "sonnet")
        self.assertEqual(DEFAULT_AGENT_CONFIG.max_tokens, 4096)
        self.assertEqual(DEFAULT_AGENT_CONFIG.window_size, 15)
        self.assertEqual(DEFAULT_AGENT_CONFIG.batch_threshold, 5)
        self.assertEqual(DEFAULT_AGENT_CONFIG.max_classification_retries, 2)


if __name__ == "__main__":
    unittest.main()
