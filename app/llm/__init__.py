"""The LLM backend package: health, discovery and one structured completion."""

from app.llm.base import (
    DiscoveryResult,
    LLMBackend,
    ProbeOutcome,
    ProviderModel,
    StructuredCallResult,
)
from app.llm.opencode_server import OpenCodeServerBackend, parse_providers


def get_llm_backend() -> LLMBackend:
    """FastAPI dependency: the configured backend, built per request.

    A function rather than a module-level instance for two reasons: a test can
    override it (the default lane must never touch a live server), and no client
    state is shared between requests.
    """
    return OpenCodeServerBackend()


__all__ = [
    "DiscoveryResult",
    "LLMBackend",
    "OpenCodeServerBackend",
    "ProbeOutcome",
    "ProviderModel",
    "StructuredCallResult",
    "get_llm_backend",
    "parse_providers",
]
