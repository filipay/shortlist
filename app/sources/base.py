"""The source-adapter port (D-18).

The core knows the shape of a job search, never the shape of a job board. One
`JobSource` implementation per board, each declaring its own capabilities,
budget and health.

Seven contract rules (ARCHITECTURE §5.2) hold for every adapter:

R1 `fetch` never raises for a source-specific failure — it returns `FetchResult`.
R2 the adapter sanitises before returning, and `RawListing` has **no** email,
   phone or credential field of any kind — PII is unrepresentable, not filtered.
R3 capabilities are declared and consulted; an unsupported filter is warned, not
   silently dropped.
R4 a full description is a separate, separately budgeted pass (`fetch_details`).
R5 the adapter never touches the database, never dedups, filters or scores.
R6 board-specific fields go in `source_extras`.
R7 adapters are keyed by `name` in the registry, resolved from the `sources`
   table at run start.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

SourceName = Literal["linkedin", "indeed", "adzuna", "glassdoor", "google"]

FetchStatus = Literal["ok", "partial", "blocked", "rate_limited", "error"]

#: Substrings that identify a *fetch-side* block rather than a parse problem.
#: Recorded and stopped on; never escalated (PITFALLS P2).
BLOCK_SIGNALS = (
    "403",
    "captcha",
    "unusual activity",
    "rate limit",
    "429",
    "forbidden",
)


@dataclass(frozen=True)
class SourceCapabilities:
    """What a board can actually do. Declared, not discovered at runtime."""

    supports_salary: bool
    supports_salary_min_filter: bool
    supports_remote_flag: bool
    supports_seniority: bool
    supports_full_description_in_search: bool
    #: LinkedIn: the full description costs one extra request per job.
    requires_second_pass_for_description: bool
    supports_offset_paging: bool
    #: Boards cap a query (~1000 upstream). `None` means "not declared".
    max_results_per_query: int | None
    #: Mutually exclusive filter groups. LinkedIn honours ONLY ONE of
    #: {hours_old, easy_apply}; supplying several is SILENTLY ignored upstream,
    #: so the compiler must warn rather than pretend the filter applied.
    exclusive_filter_groups: tuple[frozenset[str], ...] = ()


@dataclass(frozen=True)
class SearchQuery:
    """Board-agnostic search intent, already compiled from user criteria."""

    keywords: str
    location: str | None = None
    distance_miles: int | None = None
    remote_only: bool | None = None
    salary_floor: int | None = None
    seniority: tuple[str, ...] = ()
    hours_old: int | None = None
    offset: int = 0
    results_wanted: int = 50


@dataclass(frozen=True)
class FetchBudget:
    """Per-source, per-run ceiling. Enforced by the adapter, logged by the core."""

    max_requests: int
    max_results: int
    max_detail_fetches: int
    deadline: datetime


@dataclass(frozen=True)
class RawListing:
    """ONE raw observation. No dedup, no filtering, no scoring, NO PII.

    There is deliberately no `emails`, `phone`, `session` or credential field:
    JobSpy populates an `emails` column, and the only safe control is for the
    type to have nowhere to put it.
    """

    source: SourceName
    source_listing_id: str | None
    source_url: str
    direct_url: str | None
    title: str
    company_name: str | None = None
    location_raw: str | None = None
    description: str | None = None
    is_remote: bool | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_interval: str | None = None
    salary_currency: str | None = None
    salary_source: str | None = None
    posted_at: date | None = None
    job_type: tuple[str, ...] = ()
    source_extras: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FetchResult:
    """A total, never an exception. Partial success is a first-class outcome."""

    source: SourceName
    items: list[RawListing] = field(default_factory=list)
    status: FetchStatus = "ok"
    requests_used: int = 0
    error: str | None = None


def classify_transport_error(exc: BaseException) -> FetchStatus:
    """Map a transport exception to a `FetchResult.status` (never re-raises).

    Pure and dependency-free so both the transport and the adapters can use it
    without importing `jobspy`.
    """
    message = str(exc).casefold()
    if any(signal in message for signal in ("429", "rate limit", "too many requests")):
        return "rate_limited"
    if any(signal in message for signal in BLOCK_SIGNALS):
        return "blocked"
    return "error"


class JobSource(ABC):
    """The ONLY surface the pipeline depends on. One instance per board."""

    name: SourceName
    capabilities: SourceCapabilities

    @abstractmethod
    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        """Cheap liveness check for /health and the source status UI."""

    @abstractmethod
    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        """Search-shaped, bounded, failure-tolerant. Never raises."""

    async def fetch_details(
        self, refs: list[RawListing], budget: FetchBudget
    ) -> dict[str, RawListing]:
        """Optional second pass. Default: no-op. Budgeted separately (R4)."""
        return {}


def capability_warnings(
    capabilities: SourceCapabilities, query: SearchQuery
) -> list[str]:
    """Warn about filters this board cannot honour (R3) — never silently ignore."""
    warnings: list[str] = []
    if query.salary_floor is not None and not capabilities.supports_salary_min_filter:
        warnings.append(
            f"salary_floor is not pushed to {capabilities!r}; apply it as a local rule"
        )
    if query.hours_old is not None and query.remote_only is not None:
        for group in capabilities.exclusive_filter_groups:
            if {"hours_old", "easy_apply"} <= group:
                warnings.append(
                    "hours_old and easy_apply are mutually exclusive upstream; "
                    "only one will take effect"
                )
    if query.seniority and not capabilities.supports_seniority:
        warnings.append("seniority filtering is not supported by this board")
    if (
        capabilities.max_results_per_query is not None
        and query.results_wanted > capabilities.max_results_per_query
    ):
        warnings.append(
            f"results_wanted exceeds the board cap of "
            f"{capabilities.max_results_per_query}"
        )
    return warnings


__all__ = [
    "BLOCK_SIGNALS",
    "FetchBudget",
    "FetchResult",
    "FetchStatus",
    "JobSource",
    "RawListing",
    "SearchQuery",
    "SourceCapabilities",
    "SourceName",
    "capability_warnings",
    "classify_transport_error",
]
