from decimal import Decimal

from freelance_agents.core.providers.pricing import CostCalculator, ModelPricing
from freelance_agents.core.providers.types import CompletionUsage


def test_estimate_cost_combines_prompt_and_completion_pricing() -> None:
    calculator = CostCalculator(
        {
            "gpt-test": ModelPricing(
                prompt_price_per_1k=Decimal("1.00"),
                completion_price_per_1k=Decimal("2.00"),
            )
        }
    )
    usage = CompletionUsage(prompt_tokens=500, completion_tokens=250, total_tokens=750)

    cost = calculator.estimate_cost("gpt-test", usage)

    assert cost == Decimal("0.500000") + Decimal("0.500000")


def test_estimate_cost_returns_none_for_unpriced_model() -> None:
    calculator = CostCalculator({})

    cost = calculator.estimate_cost(
        "unknown-model",
        CompletionUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    )

    assert cost is None


def test_estimate_cost_with_no_pricing_table_returns_none() -> None:
    calculator = CostCalculator()

    cost = calculator.estimate_cost(
        "any-model",
        CompletionUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    )

    assert cost is None


def test_estimate_cost_handles_zero_usage() -> None:
    calculator = CostCalculator(
        {
            "gpt-test": ModelPricing(
                prompt_price_per_1k=Decimal("1.00"),
                completion_price_per_1k=Decimal("2.00"),
            )
        }
    )

    cost = calculator.estimate_cost(
        "gpt-test",
        CompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )

    assert cost == Decimal("0.000000")
