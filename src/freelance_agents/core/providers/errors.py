"""Domain errors for AI completion provider operations."""


class ProviderError(Exception):
    """Base class for completion-provider domain errors."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is misconfigured or a request is malformed."""


class ProviderAuthenticationError(ProviderError):
    """Raised when a provider rejects the configured credentials."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider reports that its rate limit was exceeded."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call does not complete within its timeout."""


class ProviderResponseError(ProviderError):
    """Raised when a provider response is rejected or has an unexpected shape."""
