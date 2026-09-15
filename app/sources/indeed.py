"""Indeed adapter — a second `JobSource` over the shared JobSpy transport.

Indeed's constraints differ from LinkedIn's (no `hours_old`/`easy_apply`
exclusivity, descriptions are returned in the search response), so it declares its
own capabilities. It shares the row mapper, so both boards produce one shape.

**The Ireland guard is the point of this module.** JobSpy's `country_indeed`
defaults to `"usa"`: omitting it returns US listings that parse perfectly, which
silently poisons both the corpus and the probe baseline (Pitfall 6). The value is
sourced from `settings.probe_country_indeed` and is never left unset.

No credential path exists here: public logged-out pages only, no login, no cookie
jar, no session-bearing request (T-01-20).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.config import settings
from app.sources._jobspy_mapping import map_jobspy_row
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

NAME = "indeed"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PROBE_URL = "https://ie.indeed.com/jobs?q=engineer&l=Ireland"
PROBE_MIN_BODY_BYTES = 2000
PROBE_STOP_SIGNALS = (
    "captcha",
    "unusual traffic",
    "additional verification",
    "sign in to continue",
)

CAPABILITIES = SourceCapabilities(
    supports_salary=True,
    # JobSpy forwards no salary-minimum filter, so a salary floor is a local rule.
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    # Indeed returns the description in the search response: no second pass.
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
    # Indeed does NOT carry LinkedIn's {hours_old, easy_apply} exclusivity.
    exclusive_filter_groups=(),
)


def _load_transport() -> Any:
    """Import the JobSpy transport on demand (see the LinkedIn adapter)."""
    from app.sources import _jobspy_transport

    return _jobspy_transport


class IndeedAdapter(JobSource):
    """One instance per board. Never touches the database, never dedups."""

    name: SourceName = "indeed"
    capabilities = CAPABILITIES

    def __init__(self, transport: Any | None = None) -> None:
        self._transport = transport

    def transport(self) -> Any:
        return self._transport if self._transport is not None else _load_transport()

    def build_kwargs(self, query: SearchQuery, budget: FetchBudget) -> dict:
        """The JobSpy kwargs for one Indeed search.

        `country_indeed` is ALWAYS set from settings — never the library default.
        """
        kwargs = dict(
            site_name="indeed",
            search_term=query.keywords,
            location=query.location,
            results_wanted=min(query.results_wanted, budget.max_results),
            is_remote=bool(query.remote_only) if query.remote_only is not None else False,
            distance=query.distance_miles if query.distance_miles is not None else 50,
            country_indeed=settings.probe_country_indeed,
            offset=query.offset,
            verbose=0,
        )
        if query.hours_old is not None:
            kwargs["hours_old"] = query.hours_old
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

        rows = list(frame) if frame is not None else []
        return FetchResult(
            source=NAME,
            items=[map_jobspy_row(row, source=NAME) for row in rows],
            status="ok",
            requests_used=1,
        )

    async def fetch_details(
        self, refs: list[RawListing], budget: FetchBudget
    ) -> dict[str, RawListing]:
        """Indeed needs no second pass: the search response carries descriptions."""
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


__all__ = ["CAPABILITIES", "IndeedAdapter"]
