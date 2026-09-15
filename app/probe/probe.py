"""TTL-cached, non-raising liveness probe over the registered adapters.

Why the cache is load-bearing: `/health` is loaded by the queue page, by the
operator and by any uptime check. Without a TTL, every page load would put a
request on a job board that bans automation — a self-inflicted DoS on the source
(T-01-31). `settings.probe_cache_ttl_seconds` is read per call, never frozen into
a constant, so the envelope stays configuration (PLAT-04).

The cache is process-local by design: it is a politeness window, not state. A
restart may re-probe once, which is the correct behaviour.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.sources import registry
from app.sources.base import JobSource

log = structlog.get_logger(__name__)

SourceStatus = Literal["ok", "degraded", "unreachable"]

#: `name -> (expires_at_monotonic, status)`.
_CACHE: dict[str, tuple[float, SourceStatus]] = {}

_VALID: frozenset[str] = frozenset({"ok", "degraded", "unreachable"})


def clear_cache() -> None:
    """Drop every cached result (tests, and an operator forcing a re-probe)."""
    _CACHE.clear()


def _ttl_seconds() -> float:
    """The cache window, read from settings on every use (PLAT-04)."""
    return float(settings.probe_cache_ttl_seconds)


def _cached(name: str, *, now: float) -> SourceStatus | None:
    entry = _CACHE.get(name)
    if entry is None:
        return None
    expires_at, status = entry
    if expires_at <= now:
        _CACHE.pop(name, None)
        return None
    return status


async def _invoke(adapter_cls: type[JobSource]) -> SourceStatus:
    """Call one adapter's `probe()`. A failure degrades that source only (R1).

    Only the exception *type* is logged: a probe error string can carry the
    request URL, and the log line is not worth that.
    """
    try:
        status = await adapter_cls().probe()
    except Exception as exc:  # noqa: BLE001 — the probe is a total function
        log.warning("probe.failed", source=adapter_cls.name, error=type(exc).__name__)
        return "unreachable"
    if status not in _VALID:
        log.warning("probe.invalid_status", source=adapter_cls.name)
        return "unreachable"
    return status


async def probe_source(name: str, *, force: bool = False) -> SourceStatus:
    """Probe one source, honouring the TTL cache unless `force` is set.

    Total: an unknown or unregistered name is `unreachable`, never an exception.
    """
    if not force:
        cached = _cached(name, now=time.monotonic())
        if cached is not None:
            return cached

    try:
        adapter_cls = registry.get(name)
    except registry.UnknownAdapterError:
        log.warning("probe.unknown_source", source=name)
        return "unreachable"

    status = await _invoke(adapter_cls)
    # Expiry is stamped *after* the probe, so a slow probe does not shorten its
    # own window.
    _CACHE[name] = (time.monotonic() + _ttl_seconds(), status)
    return status


async def _resolve_names(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None,
    names: Sequence[str] | None,
) -> list[str]:
    """Which sources to probe, in deterministic order."""
    if names is not None:
        return sorted(set(names))
    if session_factory is None:
        # DB-free path. NOTE: this probes every registered adapter, so a test
        # lane that reaches it must clear the registry first or it will touch a
        # live board.
        return sorted(registry.all_adapters())

    from app.db.repositories import source_repo  # local: keeps the probe DB-free

    async with session_factory() as session:
        return await source_repo.enabled_source_names(session)


async def _persist(
    fresh: dict[str, SourceStatus],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.db.repositories import source_repo

    async with session_factory() as session:
        for name, status in sorted(fresh.items()):
            await source_repo.record_probe_result(session, source=name, status=status)
        await session.commit()


async def probe_all(
    *,
    force: bool = False,
    names: Sequence[str] | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, SourceStatus]:
    """Probe every enabled source and return `{name: status}`, name-sorted.

    Resolution order: an explicit `names` argument; else the enabled `sources`
    rows when a `session_factory` is given (`/health`'s production path); else
    every adapter in the registry.

    Never raises. An unknown name is skipped (the pipeline degrades one board the
    same way), an adapter error becomes `unreachable` for that source only, and a
    persistence failure is logged rather than propagated — `/health` must answer
    in every case (D-08).

    Only a *freshly* probed source is written back to its `sources` row, so a
    cache hit costs no write and `last_probe_at` keeps meaning "when the probe
    actually ran".
    """
    resolved = await _resolve_names(session_factory=session_factory, names=names)
    registered = registry.all_adapters()

    results: dict[str, SourceStatus] = {}
    fresh: dict[str, SourceStatus] = {}

    for name in resolved:
        if name not in registered:
            log.warning("probe.unknown_source", source=name)
            continue
        if not force:
            cached = _cached(name, now=time.monotonic())
            if cached is not None:
                results[name] = cached
                continue
        results[name] = await probe_source(name, force=True)
        fresh[name] = results[name]

    if fresh and session_factory is not None:
        try:
            await _persist(fresh, session_factory)
        except Exception as exc:  # noqa: BLE001 — a DB failure must not break /health
            log.warning("probe.persist_failed", error=type(exc).__name__)

    return dict(sorted(results.items()))


__all__ = ["SourceStatus", "clear_cache", "probe_all", "probe_source"]
