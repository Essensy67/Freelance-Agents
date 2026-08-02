"""Tests for the OpenAI-compatible HTTP adapter, using httpx.MockTransport.

No real network calls are made; ``httpx.MockTransport`` simulates server
responses so the retry policy, error mapping, and redacted logging can be
verified offline.
"""

import httpx
import pytest

from freelance_agents.core.providers.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from freelance_agents.core.providers.types import (
    CompletionMessage,
    CompletionRequest,
    CompletionRole,
)
from freelance_agents.providers.openai_compatible import OpenAICompatibleProvider

SECRET_API_KEY = "sk-super-secret-key"
PRIVATE_MESSAGE = "please do not leak this exact prompt content"


def make_request(**overrides: object) -> CompletionRequest:
    defaults: dict[str, object] = {
        "model": "gpt-test",
        "messages": (
            CompletionMessage(role=CompletionRole.USER, content=PRIVATE_MESSAGE),
        ),
    }
    defaults.update(overrides)
    return CompletionRequest(**defaults)  # type: ignore[arg-type]


def success_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "gpt-test",
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        },
    )


def make_provider(
    handler, max_retries: int = 2, retry_backoff_seconds: float = 0.0
) -> OpenAICompatibleProvider:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    return OpenAICompatibleProvider(
        base_url="https://example.test",
        api_key=SECRET_API_KEY,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        http_client=client,
    )


def test_constructor_rejects_blank_base_url() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleProvider(base_url="   ", api_key="sk-test")


def test_constructor_rejects_blank_api_key() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleProvider(base_url="https://example.test", api_key="   ")


def test_constructor_rejects_negative_max_retries() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleProvider(
            base_url="https://example.test", api_key="sk-test", max_retries=-1
        )


async def test_complete_rejects_empty_messages() -> None:
    provider = make_provider(lambda request: success_response())

    with pytest.raises(ProviderConfigurationError):
        await provider.complete(make_request(messages=()))

    await provider.aclose()


async def test_complete_returns_normalized_response_on_success() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return success_response()

    provider = make_provider(handler)

    response = await provider.complete(make_request())

    assert response.model == "gpt-test"
    assert response.content == "hello"
    assert response.finish_reason == "stop"
    assert response.usage.prompt_tokens == 5
    assert response.usage.completion_tokens == 3
    assert response.usage.total_tokens == 8
    assert len(calls) == 1
    assert calls[0].headers["authorization"] == f"Bearer {SECRET_API_KEY}"

    await provider.aclose()


async def test_complete_retries_rate_limit_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return success_response()

    provider = make_provider(handler)

    response = await provider.complete(make_request())

    assert response.content == "hello"
    assert attempts["n"] == 2

    await provider.aclose()


async def test_complete_retries_server_error_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] <= 2:
            return httpx.Response(503, json={"error": "unavailable"})
        return success_response()

    provider = make_provider(handler, max_retries=2)

    response = await provider.complete(make_request())

    assert response.content == "hello"
    assert attempts["n"] == 3

    await provider.aclose()


async def test_complete_exhausts_retries_and_raises_rate_limit_error() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    provider = make_provider(handler, max_retries=1)

    with pytest.raises(ProviderRateLimitError):
        await provider.complete(make_request())

    assert attempts["n"] == 2

    await provider.aclose()


async def test_complete_does_not_retry_non_retryable_client_error() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    provider = make_provider(handler, max_retries=2)

    with pytest.raises(ProviderResponseError):
        await provider.complete(make_request())

    assert attempts["n"] == 1

    await provider.aclose()


@pytest.mark.parametrize("status_code", [401, 403])
async def test_complete_raises_authentication_error_without_retry(
    status_code: int,
) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(status_code, json={"error": "unauthorized"})

    provider = make_provider(handler, max_retries=2)

    with pytest.raises(ProviderAuthenticationError):
        await provider.complete(make_request())

    assert attempts["n"] == 1

    await provider.aclose()


async def test_complete_retries_timeout_then_raises_after_exhaustion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    provider = make_provider(handler, max_retries=1)

    with pytest.raises(ProviderTimeoutError):
        await provider.complete(make_request())

    await provider.aclose()


async def test_complete_raises_response_error_for_malformed_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = make_provider(handler, max_retries=0)

    with pytest.raises(ProviderResponseError):
        await provider.complete(make_request())

    await provider.aclose()


async def test_complete_raises_transport_error_for_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure", request=request)

    provider = make_provider(handler, max_retries=0)

    with pytest.raises(ProviderError):
        await provider.complete(make_request())

    await provider.aclose()


async def test_logging_never_exposes_api_key_or_message_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return success_response()

    provider = make_provider(handler)

    with caplog.at_level("INFO"):
        await provider.complete(make_request())

    assert SECRET_API_KEY not in caplog.text
    assert PRIVATE_MESSAGE not in caplog.text

    await provider.aclose()
