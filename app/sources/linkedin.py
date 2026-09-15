"""LinkedIn adapter — one `JobSource` over the shared JobSpy transport.

Board knowledge lives here (the known-stable probe URL, the capability set, the
JobSpy kwargs); the transport stays board-agnostic. `jobspy` is imported lazily
so the unit tests do not need its native toolchain.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx

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

#: The pinned JobSpy column contract (RESEARCH §Verified External Contracts 2).
#: A *missing* expected column is schema drift (signal S6).
DESIRED_ORDER = (
    "id",
    "site",
    "job_url",
    "job_url_direct",
    "title",
    "company",
    "location",
    "date_posted",
    "job_type",
    "salary_source",
    "interval",
    "min_amount",
    "max_amount",
    "currency",
    "is_remote",
    "job_level",
    "job_function",
    "listing_type",
    "emails",
    "description",
    "company_industry",
    "company_url",
    "company_logo",
    "company_url_direct",
    "company_addresses",
    "company_num_employees",
    "company_revenue",
    "company_description",
)

#: Board fields that do not deserve a core column (R6).
EXTRA_FIELDS = ("job_level", "job_function", "listing_type", "company_industry")

#: The library column that must NEVER be mapped (JobSpy populates it from the
#: description). It is read into no variable and appears in no dataclass field.
DROP_FIELDS = ("emails",)

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


def _is_missing(value: Any) -> bool:
    """True for None, NaN and NaT without importing pandas."""
    if value is None:
        return True
    try:
        return bool(value != value)
    except (TypeError, ValueError):
        return False


def _as_str(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _as_date(value: Any) -> date | None:
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_tuple(value: Any) -> tuple[str, ...]:
    if _is_missing(value):
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if not _is_missing(item))
    return (str(value),)


def _read(row: Any, key: str) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def map_jobspy_row(row: Any, *, source: str = NAME) -> RawListing:
    """Map one JobSpy row (dict or pandas Series) to a `RawListing`.

    Reads only the pinned `desired_order` fields. The `emails` column is in
    `DROP_FIELDS` and is never read into a variable — see the module docstring.
    """
    extras = {
        key: _read(row, key)
        for key in EXTRA_FIELDS
        if not _is_missing(_read(row, key))
    }
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=_as_str(_read(row, "id")),  # may legitimately be None
        source_url=_as_str(_read(row, "job_url")) or "",
        direct_url=_as_str(_read(row, "job_url_direct")),
        title=_as_str(_read(row, "title")) or "",
        company_name=_as_str(_read(row, "company")),
        location_raw=_as_str(_read(row, "location")),
        description=_as_str(_read(row, "description")),
        is_remote=_as_bool(_read(row, "is_remote")),
        salary_min=_as_float(_read(row, "min_amount")),
        salary_max=_as_float(_read(row, "max_amount")),
        salary_interval=_as_str(_read(row, "interval")),
        salary_currency=_as_str(_read(row, "currency")),
        salary_source=_as_str(_read(row, "salary_source")),
        posted_at=_as_date(_read(row, "date_posted")),
        job_type=_as_tuple(_read(row, "job_type")),
        source_extras=extras,
    )


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

        rows = list(frame) if frame is not None else []
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
