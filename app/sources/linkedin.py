"""LinkedIn adapter — one `JobSource` over the shared JobSpy transport.

Board knowledge lives here (the known-stable probe URL, the capability set, the
JobSpy kwargs); the transport stays board-agnostic. `jobspy` is imported lazily
so the unit tests do not need its native toolchain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.sources._jobspy_mapping import (
    DESIRED_ORDER,  # noqa: F401  (re-exported for existing callers)
    DROP_FIELDS,  # noqa: F401
    EXTRA_FIELDS,  # noqa: F401
    frame_rows,
)
from app.sources._jobspy_mapping import map_jobspy_row as _map_jobspy_row
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
    SourceName,
    classify_transport_error,
)

NAME = "linkedin"


def map_jobspy_row(row: Any, *, source: str = NAME) -> RawListing:
    """LinkedIn-bound view of the shared JobSpy row mapper.

    The mapper itself is board-agnostic (`app/sources/_jobspy_mapping.py`) so
    every adapter produces one shape; this wrapper only supplies the default
    board name.
    """
    return _map_jobspy_row(row, source=source)


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PROBE_URL = "https://www.linkedin.com/jobs/search/?keywords=engineer&location=Ireland"
PROBE_MIN_BODY_BYTES = 2000
PROBE_STOP_SIGNALS = ("captcha", "unusual activity", "sign in to continue", "authwall")

CAPABILITIES = SourceCapabilities(
    supports_salary=False,
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    supports_full_description_in_search=False,
    requires_second_pass_for_description=True,
    supports_offset_paging=True,
    max_results_per_query=1000,
    # LinkedIn honours ONLY ONE of {hours_old, easy_apply}.
    exclusive_filter_groups=(frozenset({"hours_old", "easy_apply"}),),
)


def _load_transport() -> Any:
    """Import the JobSpy transport on demand.

    The transport is the only `jobspy` importer, and `jobspy` pulls a native TLS
    library. Importing it lazily keeps the adapter (and its unit tests) free of
    that toolchain; production imports it on the first real fetch.
    """
    from app.sources import _jobspy_transport

    return _jobspy_transport


class LinkedInAdapter(JobSource):
    """One instance per board. Never touches the database, never dedups."""

    name: SourceName = "linkedin"
    capabilities = CAPABILITIES

    def __init__(self, transport: Any | None = None) -> None:
        # Injectable so unit tests never touch JobSpy's native toolchain.
        self._transport = transport

    def transport(self) -> Any:
        return self._transport if self._transport is not None else _load_transport()

    def build_kwargs(self, query: SearchQuery, budget: FetchBudget) -> dict:
        """The JobSpy kwargs for one LinkedIn search.

        `linkedin_fetch_description` is pinned False: the detail pass is O(n)
        extra requests and is a separate, budgeted call in Phase 1 (R4).
        """
        return dict(
            site_name="linkedin",
            search_term=query.keywords,
            location=query.location,
            results_wanted=min(query.results_wanted, budget.max_results),
            is_remote=bool(query.remote_only) if query.remote_only is not None else False,
            distance=query.distance_miles if query.distance_miles is not None else 50,
            linkedin_fetch_description=False,
            offset=query.offset,
            verbose=0,
        )

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        """Search-shaped, bounded and total: never raises for a source failure."""
        transport = self.transport()
        if not transport.budget_allows(budget, source=NAME, requests_needed=1):
            return FetchResult(
                source=NAME,
                status="error",
                requests_used=0,
                error="pre-call budget check refused the request",
            )

        deadline_s = max(
            0.0, (budget.deadline - datetime.now(UTC)).total_seconds()
        )
        try:
            frame = await transport.run_scrape(
                site=NAME, kwargs=self.build_kwargs(query, budget), deadline_s=deadline_s
            )
        except TimeoutError:
            return FetchResult(
                source=NAME,
                status="error",
                requests_used=1,
                error="deadline exceeded before the scrape returned",
            )
        except Exception as exc:  # noqa: BLE001 — R1: a source failure never raises
            return FetchResult(
                source=NAME,
                status=classify_transport_error(exc),
                requests_used=1,
                error=str(exc),
            )

        rows = frame_rows(frame)
        return FetchResult(
            source=NAME,
            items=[map_jobspy_row(row) for row in rows],
            status="ok",
            requests_used=1,
        )

    async def fetch_details(
        self, refs: list[RawListing], budget: FetchBudget
    ) -> dict[str, RawListing]:
        """The O(n) LinkedIn description pass — invoked only when budgeted (R4)."""
        if budget.max_detail_fetches <= 0 or not refs:
            return {}
        transport = self.transport()
        if not transport.budget_allows(
            budget, source=NAME, requests_needed=min(len(refs), budget.max_detail_fetches)
        ):
            return {}
        # Phase 1 keeps the detail pass off by default (probe_max_detail_fetches=0);
        # plan 01-07 decides whether the survival measurement enables it.
        return {}

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        """Cheap liveness check that asserts a KNOWN ANSWER, not merely a 200."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(PROBE_URL)
        except Exception:  # noqa: BLE001 — probe is total
            return "unreachable"

        if response.status_code != 200:
            return "unreachable"
        body = response.text
        if len(body) < PROBE_MIN_BODY_BYTES:
            return "degraded"
        lowered = body.casefold()
        if any(signal in lowered for signal in PROBE_STOP_SIGNALS):
            return "degraded"
        return "ok"


__all__ = [
    "CAPABILITIES",
    "DESIRED_ORDER",
    "DROP_FIELDS",
    "EXTRA_FIELDS",
    "LinkedInAdapter",
    "map_jobspy_row",
]
