"""Tests for pricing module."""

import unittest
from decimal import Decimal

from src.agent.pricing import MODEL_PRICING, calculate_cost


class TestModelPricing(unittest.TestCase):
    """Tests for MODEL_PRICING configuration."""

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

    def test_cache_read_cheaper_than_input(self) -> None:
        """Cache read tokens should be cheaper than input tokens."""
        for model, pricing in MODEL_PRICING.items():
            with self.subTest(model=model):
                self.assertLess(pricing.cache_read_per_1k, pricing.input_per_1k)

    def test_output_more_expensive_than_input(self) -> None:
        """Output tokens should be more expensive than input tokens."""
        for model, pricing in MODEL_PRICING.items():
            with self.subTest(model=model):
                self.assertGreater(pricing.output_per_1k, pricing.input_per_1k)


class TestCalculateCost(unittest.TestCase):
    """Tests for calculate_cost function."""

    def test_calculate_cost_haiku(self) -> None:
        """Should calculate cost correctly for haiku model."""
        # 1000 input tokens at $0.001/1k = $0.001
        # 1000 output tokens at $0.005/1k = $0.005
        # Total = $0.006
        cost = calculate_cost("haiku", input_tokens=1000, output_tokens=1000)
        self.assertEqual(cost, Decimal("0.006"))

    def test_calculate_cost_sonnet(self) -> None:
        """Should calculate cost correctly for sonnet model."""
        # 1000 input tokens at $0.003/1k = $0.003
        # 1000 output tokens at $0.015/1k = $0.015
        # Total = $0.018
        cost = calculate_cost("sonnet", input_tokens=1000, output_tokens=1000)
        self.assertEqual(cost, Decimal("0.018"))

    def test_calculate_cost_opus(self) -> None:
        """Should calculate cost correctly for opus model."""
        # 1000 input tokens at $0.005/1k = $0.005
        # 1000 output tokens at $0.025/1k = $0.025
        # Total = $0.030
        cost = calculate_cost("opus", input_tokens=1000, output_tokens=1000)
        self.assertEqual(cost, Decimal("0.030"))

    def test_calculate_cost_with_cache_read_tokens(self) -> None:
        """Should include cache read tokens in cost calculation."""
        # 1000 input at $0.001/1k = $0.001
        # 1000 output at $0.005/1k = $0.005
        # 1000 cache at $0.0001/1k = $0.0001
        # Total = $0.0061
        cost = calculate_cost(
            "haiku",
            input_tokens=1000,
            output_tokens=1000,
            cache_read_tokens=1000,
        )
        self.assertEqual(cost, Decimal("0.0061"))

    def test_calculate_cost_partial_thousands(self) -> None:
        """Should calculate cost correctly for partial thousands of tokens."""
        # 500 input tokens at $0.001/1k = $0.0005
        # 250 output tokens at $0.005/1k = $0.00125
        # Total = $0.00175
        cost = calculate_cost("haiku", input_tokens=500, output_tokens=250)
        self.assertEqual(cost, Decimal("0.00175"))

    def test_calculate_cost_zero_tokens(self) -> None:
        """Should return zero cost for zero tokens."""
        cost = calculate_cost("haiku", input_tokens=0, output_tokens=0)
        self.assertEqual(cost, Decimal("0"))

    def test_calculate_cost_large_token_count(self) -> None:
        """Should calculate cost correctly for large token counts."""
        # 100,000 input tokens at $0.003/1k = $0.30
        # 50,000 output tokens at $0.015/1k = $0.75
        # Total = $1.05
        cost = calculate_cost("sonnet", input_tokens=100_000, output_tokens=50_000)
        self.assertEqual(cost, Decimal("1.05"))

    def test_calculate_cost_case_insensitive(self) -> None:
        """Should accept model alias in any case."""
        cost_lower = calculate_cost("haiku", input_tokens=1000, output_tokens=1000)
        cost_upper = calculate_cost("HAIKU", input_tokens=1000, output_tokens=1000)
        cost_mixed = calculate_cost("Haiku", input_tokens=1000, output_tokens=1000)

        self.assertEqual(cost_lower, cost_upper)
        self.assertEqual(cost_lower, cost_mixed)

    def test_calculate_cost_unknown_model_raises_error(self) -> None:
        """Should raise ValueError for unknown model alias."""
        with self.assertRaises(ValueError) as context:
            calculate_cost("unknown_model", input_tokens=100, output_tokens=100)

        self.assertIn("Unknown model alias", str(context.exception))
        self.assertIn("unknown_model", str(context.exception))


if __name__ == "__main__":
    unittest.main()
