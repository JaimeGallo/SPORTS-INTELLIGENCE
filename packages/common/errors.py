"""Error hierarchy."""

from __future__ import annotations


class JEVSError(Exception):
    """Base class for every error raised by the platform."""


class ConfigError(JEVSError):
    """Invalid or unsafe configuration."""


class DataError(JEVSError):
    """Malformed or inconsistent data from a provider."""


class CapabilityNotSupported(JEVSError):
    """A provider was asked for something its declared capabilities do not include."""

    def __init__(self, provider: str, capability: str) -> None:
        super().__init__(f"provider '{provider}' does not declare capability '{capability}'")
        self.provider = provider
        self.capability = capability


class LeakageError(JEVSError):
    """Information not available at the prediction timestamp reached a model."""


class InvalidOdds(DataError):
    """Odds that cannot represent a real price (<= 1.0 decimal, NaN, malformed)."""


class ModelError(JEVSError):
    """The model failed to fit or to produce a valid distribution."""
