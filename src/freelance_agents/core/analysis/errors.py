"""Domain errors for order analysis and task decomposition."""


class AnalysisError(Exception):
    """Base class for order-analysis domain errors."""


class AnalysisValidationError(AnalysisError):
    """Raised when an order is not in an analyzable state, or is too large.

    Covers both "this project cannot be analyzed right now" (no order, no
    conversation) and the bounded-prompt rule: an order title or description
    that exceeds the configured limit is rejected before any provider call.
    """


class AnalysisResponseError(AnalysisError):
    """Raised when a provider response is not the expected task-plan JSON shape.

    This is a fail-closed error: no tasks are created and the caller may
    retry, since nothing was persisted for the failed attempt except the
    private audit record of what was sent and received.
    """
