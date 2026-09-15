"""The adapter registry (R7).

Keyed by `JobSource.name`. Adding a board is: implement `JobSource`, register it,
insert a `sources` row, run it — no pipeline edit and no schema change (SRC-04).

The *running* sources for a given run are the enabled rows of the `sources`
table; the registry only answers "which adapter class implements this name".
"""

from __future__ import annotations

from app.sources.base import JobSource

_REGISTRY: dict[str, type[JobSource]] = {}


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


def get(name: str) -> type[JobSource] | None:
    return _REGISTRY.get(name)


def all_adapters() -> dict[str, type[JobSource]]:
    """A copy, so a caller cannot mutate the registry by accident."""
    return dict(_REGISTRY)


# Registration is performed by importing the adapter modules — the registry is
# never hand-populated, so a new module is registered by being imported here.
from app.sources import linkedin  # noqa: E402

register(linkedin.LinkedInAdapter)


__all__ = ["all_adapters", "clear", "get", "register", "unregister"]
