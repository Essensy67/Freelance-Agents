"""Tests for ``RecordingCompletionProvider`` against a real SQLite database."""

from decimal import Decimal
from pathlib import Path

import pytest
from provider_fakes import FakeCompletionProvider

from freelance_agents.core.providers.errors import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from freelance_agents.core.providers.pricing import CostCalculator, ModelPricing
from freelance_agents.core.providers.types import (
    CompletionMessage,
    CompletionRequest,
    CompletionResponse,
    CompletionRole,
    CompletionUsage,
)
from freelance_agents.database.manager import Database
from freelance_agents.database.models import ProviderCallStatus
from freelance_agents.database.provider_calls import RecordingCompletionProvider
from freelance_agents.database.repositories import ProviderCallRepository


def sqlite_url(path: Path) -> str:
    """Return an async SQLite URL for a temporary path."""
    return f"sqlite+aiosqlite:///{path}"


def make_request() -> CompletionRequest:
    return CompletionRequest(
        model="gpt-test",
        messages=(CompletionMessage(role=CompletionRole.USER, content="hi"),),
    )


async def test_successful_call_is_persisted_with_usage_latency_and_cost(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "calls.db"))
    await database.initialize()
    response = CompletionResponse(
        model="gpt-test",
        content="hello",
        usage=CompletionUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        finish_reason="stop",
    )
    cost_calculator = CostCalculator(
        {
            "gpt-test": ModelPricing(
                prompt_price_per_1k=Decimal("1.00"),
                completion_price_per_1k=Decimal("2.00"),
            )
        }
    )
    recorder = RecordingCompletionProvider(
        FakeCompletionProvider(response=response),
        database,
        cost_calculator,
        provider_name="fake",
    )

    result = await recorder.complete(make_request())

    assert result is response

    async with database.session() as session:
        records = await ProviderCallRepository(session).list()

    assert len(records) == 1
    record = records[0]
    assert record.provider == "fake"
    assert record.model == "gpt-test"
    assert record.status is ProviderCallStatus.SUCCESS
    assert record.prompt_tokens == 10
    assert record.completion_tokens == 20
    assert record.total_tokens == 30
    assert record.latency_ms >= 0
    assert record.estimated_cost == Decimal("0.050000")
    assert record.error_type is None
    assert record.error_message is None

    await database.close()


async def test_successful_call_with_unpriced_model_persists_null_cost(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "unpriced.db"))
    await database.initialize()
    response = CompletionResponse(
        model="gpt-test",
        content="hello",
        usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    recorder = RecordingCompletionProvider(
        FakeCompletionProvider(response=response),
        database,
        CostCalculator(),
        provider_name="fake",
    )

    await recorder.complete(make_request())

    async with database.session() as session:
        records = await ProviderCallRepository(session).list()

    assert records[0].estimated_cost is None

    await database.close()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ProviderRateLimitError("rate limited"), ProviderCallStatus.RATE_LIMITED),
        (ProviderTimeoutError("timed out"), ProviderCallStatus.TIMEOUT),
        (ProviderResponseError("bad response"), ProviderCallStatus.ERROR),
    ],
)
async def test_failed_call_is_persisted_and_reraised(
    tmp_path: Path, error, expected_status
) -> None:
    database = Database(sqlite_url(tmp_path / "errors.db"))
    await database.initialize()
    recorder = RecordingCompletionProvider(
        FakeCompletionProvider(error=error),
        database,
        CostCalculator(),
        provider_name="fake",
    )

    with pytest.raises(type(error)):
        await recorder.complete(make_request())

    async with database.session() as session:
        records = await ProviderCallRepository(session).list()

    assert len(records) == 1
    record = records[0]
    assert record.status is expected_status
    assert record.prompt_tokens == 0
    assert record.completion_tokens == 0
    assert record.total_tokens == 0
    assert record.estimated_cost is None
    assert record.error_type == type(error).__name__
    assert record.error_message == str(error)

    await database.close()


async def test_persistence_failure_does_not_mask_successful_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(sqlite_url(tmp_path / "swallow-success.db"))
    await database.initialize()
    response = CompletionResponse(
        model="gpt-test",
        content="hello",
        usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    recorder = RecordingCompletionProvider(
        FakeCompletionProvider(response=response),
        database,
        CostCalculator(),
        provider_name="fake",
    )

    async def failing_create(self, **values: object) -> None:
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr(ProviderCallRepository, "create", failing_create)

    result = await recorder.complete(make_request())

    assert result is response

    await database.close()


async def test_persistence_failure_does_not_mask_original_provider_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(sqlite_url(tmp_path / "swallow-error.db"))
    await database.initialize()
    recorder = RecordingCompletionProvider(
        FakeCompletionProvider(error=ProviderRateLimitError("rate limited")),
        database,
        CostCalculator(),
        provider_name="fake",
    )

    async def failing_create(self, **values: object) -> None:
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr(ProviderCallRepository, "create", failing_create)

    with pytest.raises(ProviderRateLimitError):
        await recorder.complete(make_request())

    await database.close()


async def test_aclose_delegates_to_wrapped_provider_when_present(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "aclose.db"))
    await database.initialize()

    class ClosableFakeProvider(FakeCompletionProvider):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    inner = ClosableFakeProvider(
        response=CompletionResponse(
            model="gpt-test",
            content="hi",
            usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
    )
    recorder = RecordingCompletionProvider(inner, database, CostCalculator(), "fake")

    await recorder.aclose()

    assert inner.closed is True

    await database.close()
