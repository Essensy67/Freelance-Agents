"""Estimate the monetary cost of a completion call from its token usage."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from freelance_agents.core.providers.types import CompletionUsage

_COST_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-1,000-token prompt and completion prices for one model."""

    prompt_price_per_1k: Decimal
    completion_price_per_1k: Decimal


class CostCalculator:
    """Estimate call cost from a per-model pricing table.

    Pricing changes over time and varies by deployment; construct this with
    the operator's current rates rather than relying on hardcoded defaults.
    """

    def __init__(self, pricing: Mapping[str, ModelPricing] | None = None) -> None:
        self._pricing = dict(pricing) if pricing is not None else {}

    def estimate_cost(self, model: str, usage: CompletionUsage) -> Decimal | None:
        """Return the estimated cost for ``usage``, or ``None`` if unpriced."""
        pricing = self._pricing.get(model)
        if pricing is None:
            return None
        prompt_cost = (
            Decimal(usage.prompt_tokens) / Decimal(1000)
        ) * pricing.prompt_price_per_1k
        completion_cost = (
            Decimal(usage.completion_tokens) / Decimal(1000)
        ) * pricing.completion_price_per_1k
        return (prompt_cost + completion_cost).quantize(_COST_QUANTUM)
