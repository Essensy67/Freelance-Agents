"""An OpenAI-compatible HTTP adapter for the completion provider port.

Talks to any HTTP API that implements the OpenAI chat-completions request
and response shape. Validates its configuration eagerly, retries transient
failures with backoff, and never logs credentials or message content.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from freelance_agents.core.providers.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from freelance_agents.core.providers.types import (
    CompletionRequest,
    CompletionResponse,
    CompletionUsage,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class OpenAICompatibleProvider:
    """Serve completions through an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        http_client: httpx.AsyncClient | None = None,
        provider_name: str = "openai_compatible",
    ) -> None:
        """Validate configuration and construct the underlying HTTP client."""
        if not base_url.strip():
            raise ProviderConfigurationError("Provider base URL must not be blank")
        if not api_key.strip():
            raise ProviderConfigurationError("Provider API key must not be blank")
        if max_retries < 0:
            raise ProviderConfigurationError("max_retries must not be negative")

        self.provider_name = provider_name
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for ``request``, retrying transient failures."""
        if not request.messages:
            raise ProviderConfigurationError(
                "Completion request must include at least one message"
            )
        payload = _build_payload(request)

        last_error: ProviderError = ProviderError("Provider call did not complete")
        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                response = await self._client.post(
                    "/chat/completions", json=payload, headers=self._headers
                )
            except httpx.TimeoutException:
                latency_ms = _elapsed_ms(start)
                last_error = ProviderTimeoutError(
                    f"{self.provider_name} request timed out"
                )
                logger.warning(
                    "%s request timed out (attempt %d/%d, %d ms)",
                    self.provider_name,
                    attempt + 1,
                    self._max_retries + 1,
                    latency_ms,
                )
            except httpx.HTTPError as error:
                latency_ms = _elapsed_ms(start)
                last_error = ProviderError(
                    f"{self.provider_name} request failed: {type(error).__name__}"
                )
                logger.warning(
                    "%s transport error (attempt %d/%d, %d ms): %s",
                    self.provider_name,
                    attempt + 1,
                    self._max_retries + 1,
                    latency_ms,
                    type(error).__name__,
                )
            else:
                latency_ms = _elapsed_ms(start)
                result = self._handle_response(response, request.model, latency_ms)
                if isinstance(result, CompletionResponse):
                    return result
                last_error = result
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    raise last_error

            if attempt < self._max_retries:
                await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))

        raise last_error

    def _handle_response(
        self, response: httpx.Response, model: str, latency_ms: int
    ) -> CompletionResponse | ProviderError:
        status = response.status_code
        if status in (401, 403):
            logger.warning(
                "%s rejected credentials (status %d, %d ms)",
                self.provider_name,
                status,
                latency_ms,
            )
            return ProviderAuthenticationError(
                f"{self.provider_name} rejected credentials (status {status})"
            )
        if status == 429:
            logger.warning(
                "%s reported rate limiting (status %d, %d ms)",
                self.provider_name,
                status,
                latency_ms,
            )
            return ProviderRateLimitError(f"{self.provider_name} rate limit exceeded")
        if status >= 500:
            logger.warning(
                "%s server error (status %d, %d ms)",
                self.provider_name,
                status,
                latency_ms,
            )
            return ProviderError(f"{self.provider_name} server error (status {status})")
        if status >= 400:
            logger.warning(
                "%s rejected request (status %d, %d ms)",
                self.provider_name,
                status,
                latency_ms,
            )
            return ProviderResponseError(
                f"{self.provider_name} request rejected (status {status})"
            )

        logger.info(
            "%s completed (model=%s, status=%d, %d ms)",
            self.provider_name,
            model,
            status,
            latency_ms,
        )
        return _parse_response(response, model)

    async def aclose(self) -> None:
        """Close the underlying HTTP client when this adapter owns it."""
        if self._owns_client:
            await self._client.aclose()


def _build_payload(request: CompletionRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
        ],
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    return payload


def _parse_response(response: httpx.Response, model: str) -> CompletionResponse:
    try:
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason")
        usage_data = data.get("usage") or {}
        usage = CompletionUsage(
            prompt_tokens=int(usage_data.get("prompt_tokens", 0)),
            completion_tokens=int(usage_data.get("completion_tokens", 0)),
            total_tokens=int(usage_data.get("total_tokens", 0)),
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ProviderResponseError(
            "Provider returned an unexpected response shape"
        ) from error
    return CompletionResponse(
        model=str(data.get("model", model)),
        content=content,
        usage=usage,
        finish_reason=finish_reason,
    )


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
