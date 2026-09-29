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
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any, Literal

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
    #: "Easy apply only". Exists so the LinkedIn {hours_old, easy_apply}
    #: exclusivity is expressible at all — the board silently honours only one.
    easy_apply: bool | None = None
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
    #: The board's level collapsed to `junior`/`mid`/`senior`/`lead`, or `None`
    #: when the board gives nothing usable. The normalise stage may fill it from a
    #: conservative title heuristic; it is never a fabricated guess.
    seniority: str | None = None
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


def classify_response(
    *,
    status_code: int | None,
    parsed_items: int,
    stop_signal: str | None = None,
    transport_error: str | None = None,
) -> tuple[bool, str]:
    """Classify one completed request as fetch-side or parse-side (signal S5).

    A *fetch* problem (403, 429, a stop signal, a suspiciously empty body) and a
    *parse* problem (a valid page, no matching rows) need opposite fixes and both
    present as empty data. A `blocked`/`rate_limited` outcome with a plausible body
    is the silent-breakage case and must classify as fetch-side.

    A raised transport failure (a connection reset, a timeout) is also fetch-side:
    `transport_error` carries its message, so a fetch failure is never
    misrecorded as a parse miss. It takes precedence over the other evidence.

    Lives here rather than in the transport so the survival signals can use it
    without importing `jobspy` (the transport module is the only `jobspy` importer
    and cannot be loaded without its native toolchain).

    JobSpy does not surface the HTTP status, so `status_code=None` is the normal
    production case: the classification then rests on the stop signal and the
    parsed row count, and the note says so rather than implying a 200.
    """
    if transport_error:
        return False, f"fetch-side: transport error: {transport_error}"
    if stop_signal:
        return (
            False,
            f"fetch-side: stop signal {stop_signal!r}; recorded and stopped, never retried",
        )
    if status_code in (401, 403):
        return False, f"fetch-side: blocked with HTTP {status_code}"
    if status_code == 429:
        return False, "fetch-side: rate limited (HTTP 429)"
    if status_code is not None and status_code >= 500:
        return False, f"fetch-side: upstream error (HTTP {status_code})"
    if parsed_items == 0:
        return False, "parse-side: the request returned no rows"
    where = f"HTTP {status_code}" if status_code is not None else "no observable status"
    return True, f"ok: {where} returned {parsed_items} rows"


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


@dataclass(frozen=True)
class CapabilityWarning:
    """A requested filter a board cannot honour, recorded rather than dropped."""

    source: str
    filter_name: str
    reason: str


@dataclass(frozen=True)
class CompiledQuery:
    """A `SearchQuery` that the board can actually execute, plus its warnings."""

    query: SearchQuery
    warnings: tuple[CapabilityWarning, ...] = ()


def _filter_is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (tuple, list, set, frozenset, dict)):
        return len(value) > 0
    return True


def compile_query_for_source(
    query: SearchQuery, capabilities: SourceCapabilities, *, source: str
) -> CompiledQuery:
    """Compile one board-agnostic query against a board's declared capabilities (R3).

    Silently dropping a filter would corrupt the "why is this in my queue?" story:
    the user would believe a filter was applied when it was not. Every dropped or
    unrepresentable filter therefore becomes a `CapabilityWarning` naming the
    source and the filter.

    `exclusive_filter_groups` are enforced: at most one member of each group
    survives, chosen deterministically (alphabetically first), and every dropped
    sibling is warned about.

    Warnings are ordered by `(source, filter_name)` so identical inputs always
    produce identical run records.
    """
    warnings: list[CapabilityWarning] = []
    updates: dict[str, Any] = {}

    # 1. Filters this board cannot express at all.
    if query.salary_floor is not None and not capabilities.supports_salary_min_filter:
        warnings.append(
            CapabilityWarning(
                source, "salary_floor", "the board has no salary-minimum filter"
            )
        )
        updates["salary_floor"] = None

    if query.seniority and not capabilities.supports_seniority:
        warnings.append(
            CapabilityWarning(source, "seniority", "the board has no seniority filter")
        )
        updates["seniority"] = ()

    if query.remote_only is not None and not capabilities.supports_remote_flag:
        warnings.append(
            CapabilityWarning(source, "remote_only", "the board has no remote filter")
        )
        updates["remote_only"] = None

    # 2. Mutually exclusive groups: keep the alphabetically-first, warn the rest.
    for group in capabilities.exclusive_filter_groups:
        present = sorted(
            name
            for name in group
            if hasattr(query, name) and _filter_is_present(getattr(query, name))
        )
        for dropped in present[1:]:
            warnings.append(
                CapabilityWarning(
                    source,
                    dropped,
                    f"mutually exclusive with {present[0]} upstream; it would be ignored",
                )
            )
            updates[dropped] = None

    compiled = replace(query, **updates) if updates else query
    ordered = tuple(sorted(warnings, key=lambda item: (item.source, item.filter_name)))
    return CompiledQuery(query=compiled, warnings=ordered)


def capability_warnings(
    capabilities: SourceCapabilities, query: SearchQuery
) -> list[str]:
    """Backwards-compatible plain-text view of `compile_query_for_source`'s warnings."""
    return [
        f"{warning.filter_name}: {warning.reason}"
        for warning in compile_query_for_source(
            query, capabilities, source=""
        ).warnings
    ]


__all__ = [
    "BLOCK_SIGNALS",
    "CapabilityWarning",
    "CompiledQuery",
    "FetchBudget",
    "FetchResult",
    "FetchStatus",
    "JobSource",
    "RawListing",
    "SearchQuery",
    "SourceCapabilities",
    "SourceName",
    "capability_warnings",
    "classify_response",
    "classify_transport_error",
    "compile_query_for_source",
]
