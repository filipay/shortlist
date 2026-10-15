"""The adapter registry (R7 / SRC-04).

Keyed by `JobSource.name`. **Adding a source is a one-module change:**

    1. implement `JobSource` in `app/sources/<board>.py`
    2. `register(YourAdapter)` it (see the bottom of this module)
    3. insert a `sources` row (the running sources are its enabled rows)
    4. run it

No edit to `app/pipeline/` and no schema change. `tests/sources/test_registry.py`
proves that claim with a third adapter defined entirely inside the test.

Registration happens by importing the adapter modules — the registry is never
hand-populated — so importing this module is what makes the boards available.
"""

from __future__ import annotations

from app.sources.base import JobSource

_REGISTRY: dict[str, type[JobSource]] = {}


class UnknownAdapterError(KeyError):
    """No adapter is registered under that name."""


def register(adapter_cls: type[JobSource]) -> type[JobSource]:
    """Register (or replace) an adapter class under its `name`."""
    _REGISTRY[adapter_cls.name] = adapter_cls
    return adapter_cls


def unregister(name: str) -> None:
    """Remove an adapter. Used by tests and by feature-flagged sources."""
    _REGISTRY.pop(name, None)


def clear() -> None:
    """Drop every registration. Tests restore the snapshot afterwards."""
    _REGISTRY.clear()


def get(name: str) -> type[JobSource]:
    """Resolve an adapter class by board name.

    Raises `UnknownAdapterError` (rather than returning `None`) so a typo or a
    `sources` row with no implementation fails loudly at the call site.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownAdapterError(
            f"no adapter registered for source {name!r}; registered: {sorted(_REGISTRY)}"
        ) from None


def all_adapters() -> dict[str, type[JobSource]]:
    """A copy, in deterministic (name-sorted) order."""
    return {name: _REGISTRY[name] for name in sorted(_REGISTRY)}


# Registration is performed by importing the adapter modules — a new board is
# registered by being imported here.
from app.sources import (  # noqa: E402
    arbeitnow,
    bayt,
    glassdoor,
    indeed,
    jobicy,
    linkedin,
    remotive,
)

register(linkedin.LinkedInAdapter)
register(indeed.IndeedAdapter)
register(glassdoor.GlassdoorAdapter)
register(bayt.BaytAdapter)
register(arbeitnow.ArbeitnowAdapter)
register(remotive.RemotiveAdapter)
register(jobicy.JobicyAdapter)


__all__ = [
    "UnknownAdapterError",
    "all_adapters",
    "clear",
    "get",
    "register",
    "unregister",
]
