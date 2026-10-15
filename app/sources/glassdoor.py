"""Glassdoor adapter — a third `JobSource` over the shared JobSpy transport.

Modeled on the LinkedIn adapter: Glassdoor returns no description in the search
response, so the (budgeted-off) detail pass pattern applies. JobSpy's Glassdoor
scraper honours `hours_old` (as `fromAge` days), `easy_apply` and offset paging.

Requires `python-jobspy >= 1.3.0`: the version pinned in the published image
returns zero rows for Glassdoor; the current release scrapes it fine.

No credential path exists here: public logged-out pages only, no login, no
cookie jar (same rule as the other adapters, T-01-20).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.sources._jobspy_mapping import frame_rows
from app.sources._jobspy_mapping import map_jobspy_row as _map_jobspy_row
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
    SourceName,
    classify_response,
    classify_transport_error,
)

NAME = "glassdoor"


def map_jobspy_row(row: Any, *, source: str = NAME) -> RawListing:
    """Glassdoor-bound view of the shared JobSpy row mapper."""
    return _map_jobspy_row(row, source=source)


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PROBE_URL = "https://www.glassdoor.ie/"
PROBE_MIN_BODY_BYTES = 2000
PROBE_STOP_SIGNALS = (
    "captcha",
    "unusual activity",
    "sign in to continue",
    "authwall",
    "access denied",
    "robot check",
)

CAPABILITIES = SourceCapabilities(
    # JobSpy's Glassdoor scraper surfaces min/max/interval on many rows.
    supports_salary=True,
    # JobSpy forwards no salary-minimum filter, so a salary floor is a local rule.
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    # Descriptions are not present in the search response.
    supports_full_description_in_search=False,
    requires_second_pass_for_description=True,
    supports_offset_paging=True,
    max_results_per_query=1000,
    # Glassdoor carries `hours_old` (fromAge) and `easy_apply` as separate
    # filters; JobSpy forwards both, so no exclusivity group is declared.
    exclusive_filter_groups=(),
)


def _load_transport() -> Any:
    """Import the JobSpy transport on demand (see the LinkedIn adapter)."""
    from app.sources import _jobspy_transport

    return _jobspy_transport


class GlassdoorAdapter(JobSource):
    """One instance per board. Never touches the database, never dedups."""

    name: SourceName = "glassdoor"
    capabilities = CAPABILITIES

    def __init__(self, transport: Any | None = None) -> None:
        self._transport = transport

    def transport(self) -> Any:
        return self._transport if self._transport is not None else _load_transport()

    def build_kwargs(self, query: SearchQuery, budget: FetchBudget) -> dict:
        """The JobSpy kwargs for one Glassdoor search."""
        kwargs = dict(
            site_name="glassdoor",
            search_term=query.keywords,
            location=query.location,
            results_wanted=min(query.results_wanted, budget.max_results),
            is_remote=bool(query.remote_only) if query.remote_only is not None else False,
            distance=query.distance_miles if query.distance_miles is not None else 50,
            offset=query.offset,
            verbose=0,
        )
        if query.hours_old is not None:
            kwargs["hours_old"] = query.hours_old
        if query.easy_apply is not None:
            kwargs["easy_apply"] = query.easy_apply
        return kwargs

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
        if not rows:
            # An empty frame is NOT a clean success (CR-01, same as the others).
            _, note = classify_response(status_code=None, parsed_items=0)
            return FetchResult(
                source=NAME,
                status="partial",
                requests_used=1,
                error=note,
            )
        return FetchResult(
            source=NAME,
            items=[map_jobspy_row(row) for row in rows],
            status="ok",
            requests_used=1,
        )

    async def fetch_details(
        self, refs: list[RawListing], budget: FetchBudget
    ) -> dict[str, RawListing]:
        """Phase 1 keeps the detail pass off by default (probe_max_detail_fetches=0)."""
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


__all__ = ["CAPABILITIES", "GlassdoorAdapter"]
