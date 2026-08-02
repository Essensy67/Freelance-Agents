"""The provider-neutral async completion port.

Any application service that needs an AI completion depends only on
``CompletionProvider``, never on a concrete SDK or HTTP client. Concrete
adapters live in the infrastructure ``providers`` package; a persisting
decorator lives in ``database.provider_calls``.
"""

from typing import Protocol

from freelance_agents.core.providers.types import CompletionRequest, CompletionResponse


class CompletionProvider(Protocol):
    """Serve one normalized completion request."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for ``request``, or raise a ``ProviderError``."""
