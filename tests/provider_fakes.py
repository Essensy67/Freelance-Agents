"""A configurable in-memory completion provider double for offline tests."""

from freelance_agents.core.providers.errors import ProviderError
from freelance_agents.core.providers.types import CompletionRequest, CompletionResponse


class FakeCompletionProvider:
    """Return a canned response or raise a canned error for every call."""

    def __init__(
        self,
        *,
        response: CompletionResponse | None = None,
        error: ProviderError | None = None,
    ) -> None:
        if response is None and error is None:
            raise ValueError("FakeCompletionProvider needs a response or an error")
        self._response = response
        self._error = error
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Record the request, then return the canned response or raise the error."""
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response
