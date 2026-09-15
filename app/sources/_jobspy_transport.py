"""The shared JobSpy transport — the ONLY module in the repository that imports
`jobspy` (D-18 / AP1).

Why the boundary exists: every board-specific breakage (a renamed field, a new
block page, a rate limit) is then a change inside this module plus the board's
adapter, never a codebase-wide risk.

**`asyncio.to_thread` is not cancellable.** JobSpy is synchronous and spawns its
own internal `ThreadPoolExecutor`, so `scrape_jobs` must never run on the event
loop. On the outer `wait_for` timeout the worker thread keeps running to
completion in the background: the timeout protects the *UI*, it does not reclaim
the thread. JobSpy's `scrape_jobs()` also does **not** forward
`ScraperInput.request_timeout` (it accepts `**kwargs` and ignores them), so the
only reliable budget control is the **pre-call** decision in `budget_allows()`.

The module is imported lazily by the adapters (see `LinkedInAdapter`). That keeps
the unit-test path free of JobSpy's native toolchain (`tls_client` loads a shared
library and depends on `libresolv`), while production — where the dependency is
installed — behaves exactly as a direct top-level import would.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import jobspy

from app.sources._ledger import (  # noqa: F401  (re-exported below)
    RequestOutcome,
    record_fetch_outcome,
    record_source_request,
)
from app.sources.base import (
    FetchBudget,
    FetchStatus,
    classify_response,  # noqa: F401  (re-exported below)
    classify_transport_error,
)

#: UI-protection guard used when a caller does not supply a shorter deadline.
DEFAULT_DEADLINE_SECONDS = 180.0


async def run_scrape(*, site: str, kwargs: dict, deadline_s: float) -> Any:
    """Invoke `jobspy.scrape_jobs` off the event loop, bounded by `deadline_s`.

    One call = one board. Never pass a `site_name` list: that produces a single
    failure domain and destroys per-board budget/health attribution (AP16).

    `site` wins over anything in `kwargs`, so a caller-supplied `site_name`
    cannot both duplicate the keyword and silently target the wrong board.
    """
    payload = {**kwargs, "site_name": site}
    return await asyncio.wait_for(
        asyncio.to_thread(jobspy.scrape_jobs, **payload),
        timeout=deadline_s,
    )


def budget_allows(
    budget: FetchBudget, *, source: str, requests_needed: int
) -> bool:
    """The PRE-CALL budget decision.

    This is the real control, because neither the library timeout nor
    `asyncio.to_thread` can be relied on to stop work already started.
    """
    if requests_needed <= 0:
        return False
    if budget.max_requests <= 0:
        return False
    return requests_needed <= budget.max_requests


def remaining_seconds(
    budget: FetchBudget, *, now: datetime | None = None
) -> float:
    """Seconds left before `budget.deadline`; never negative."""
    moment = now or datetime.now(UTC)
    return max(0.0, (budget.deadline - moment).total_seconds())


def classify_failure(exc: BaseException) -> tuple[FetchStatus, str]:
    """Return `(status, note)` for a transport failure. Never re-raises."""
    status = classify_transport_error(exc)
    return status, f"fetch-side: {type(exc).__name__}: {exc}"


__all__ = [
    "DEFAULT_DEADLINE_SECONDS",
    "RequestOutcome",
    "budget_allows",
    "classify_failure",
    "classify_response",
    "record_fetch_outcome",
    "record_source_request",
    "remaining_seconds",
    "run_scrape",
]
