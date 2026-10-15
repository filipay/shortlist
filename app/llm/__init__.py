"""The LLM backend package: health, discovery and one structured completion."""

from app.config import settings
from app.llm.base import (
    DiscoveryResult,
    LLMBackend,
    ProbeOutcome,
    ProviderModel,
    StructuredCallResult,
)
from app.llm.opencode_server import OpenCodeServerBackend, parse_providers


def auth_configured() -> bool:
    """Is an opencode server password configured?

    The ONE definition of this fact: `/health` and the queue's health strip both
    read it, so the report and the strip cannot disagree (D-138). The app only
    CONSUMES `OPENCODE_SERVER_PASSWORD` — the server is user-managed; the app
    never generates, stores or emits it.
    """
    return bool(settings.opencode_server_password)


def get_llm_backend() -> LLMBackend:
    """FastAPI dependency: the configured backend, built per request.

    A function rather than a module-level instance for two reasons: a test can
    override it (the default lane must never touch a live server), and no client
    state is shared between requests.
    """
    from app.db.session import get_session_factory

    return OpenCodeServerBackend(selection_session_factory=get_session_factory())


__all__ = [
    "DiscoveryResult",
    "LLMBackend",
    "OpenCodeServerBackend",
    "ProbeOutcome",
    "ProviderModel",
    "StructuredCallResult",
    "auth_configured",
    "get_llm_backend",
    "parse_providers",
]
