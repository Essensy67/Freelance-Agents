"""Persist every AI completion provider call without its prompt/response body.

``RecordingCompletionProvider`` decorates any ``CompletionProvider``, timing
each call, estimating its cost, and persisting a ``ProviderCallModel`` row
for every attempt, success or failure. It implements ``CompletionProvider``
itself, so callers depend on the same port whether or not calls are recorded.
A persistence failure is logged and swallowed rather than masking the
underlying provider result or error.
"""

import logging
import time
from decimal import Decimal

from freelance_agents.core.providers.errors import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from freelance_agents.core.providers.port import CompletionProvider
from freelance_agents.core.providers.pricing import CostCalculator
from freelance_agents.core.providers.types import (
    CompletionRequest,
    CompletionResponse,
    CompletionUsage,
)
from freelance_agents.database.manager import Database
from freelance_agents.database.models import ProviderCallStatus
from freelance_agents.database.repositories import ProviderCallRepository

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[ProviderError], ProviderCallStatus] = {
    ProviderTimeoutError: ProviderCallStatus.TIMEOUT,
    ProviderRateLimitError: ProviderCallStatus.RATE_LIMITED,
}


class RecordingCompletionProvider:
    """Decorate a ``CompletionProvider`` with latency, cost, and outcome persistence."""

    def __init__(
        self,
        provider: CompletionProvider,
        database: Database,
        cost_calculator: CostCalculator,
        provider_name: str,
    ) -> None:
        self._provider = provider
        self._database = database
        self._cost_calculator = cost_calculator
        self._provider_name = provider_name

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Call the wrapped provider, then persist a record of the attempt."""
        start = time.monotonic()
        try:
            response = await self._provider.complete(request)
        except ProviderError as error:
            await self._record(
                request,
                status=_status_for_error(error),
                latency_ms=_elapsed_ms(start),
                usage=None,
                estimated_cost=None,
                error=error,
            )
            raise

        estimated_cost = self._cost_calculator.estimate_cost(
            request.model, response.usage
        )
        await self._record(
            request,
            status=ProviderCallStatus.SUCCESS,
            latency_ms=_elapsed_ms(start),
            usage=response.usage,
            estimated_cost=estimated_cost,
            error=None,
        )
        return response

    async def aclose(self) -> None:
        """Close the wrapped provider's resources, if it exposes ``aclose``."""
        aclose = getattr(self._provider, "aclose", None)
        if aclose is not None:
            await aclose()

    async def _record(
        self,
        request: CompletionRequest,
        *,
        status: ProviderCallStatus,
        latency_ms: int,
        usage: CompletionUsage | None,
        estimated_cost: Decimal | None,
        error: ProviderError | None,
    ) -> None:
        try:
            async with self._database.session() as session:
                await ProviderCallRepository(session).create(
                    provider=self._provider_name,
                    model=request.model,
                    status=status,
                    prompt_tokens=usage.prompt_tokens if usage is not None else 0,
                    completion_tokens=(
                        usage.completion_tokens if usage is not None else 0
                    ),
                    total_tokens=usage.total_tokens if usage is not None else 0,
                    latency_ms=latency_ms,
                    estimated_cost=estimated_cost,
                    error_type=type(error).__name__ if error is not None else None,
                    error_message=str(error) if error is not None else None,
                )
        except Exception:
            logger.error(
                "Failed to persist provider call record for model %s", request.model
            )


def _status_for_error(error: ProviderError) -> ProviderCallStatus:
    return _STATUS_BY_ERROR.get(type(error), ProviderCallStatus.ERROR)


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
