"""Provider-neutral AI completion domain types."""

from freelance_agents.core.providers.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from freelance_agents.core.providers.port import CompletionProvider
from freelance_agents.core.providers.pricing import CostCalculator, ModelPricing
from freelance_agents.core.providers.types import (
    CompletionMessage,
    CompletionRequest,
    CompletionResponse,
    CompletionRole,
    CompletionUsage,
)

__all__ = [
    "CompletionMessage",
    "CompletionProvider",
    "CompletionRequest",
    "CompletionResponse",
    "CompletionRole",
    "CompletionUsage",
    "CostCalculator",
    "ModelPricing",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTimeoutError",
]
