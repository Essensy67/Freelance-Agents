"""Provider-neutral request, response, and usage types.

Normalized so that no business workflow needs to import a concrete AI SDK
or know which HTTP-compatible provider ultimately serves a request.
"""

from dataclasses import dataclass
from enum import StrEnum


class CompletionRole(StrEnum):
    """Normalized authorship role for one message in a completion request."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class CompletionMessage:
    """One normalized message within a completion request."""

    role: CompletionRole
    content: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """A provider-neutral request for one completion."""

    model: str
    messages: tuple[CompletionMessage, ...]
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class CompletionUsage:
    """Normalized token usage for one completion call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    """A provider-neutral completion result."""

    model: str
    content: str
    usage: CompletionUsage
    finish_reason: str | None = None
