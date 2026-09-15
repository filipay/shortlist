"""Survival signals S1-S6 and the Adzuna promotion condition (D-01..D-04).

The board-agnostic half of the probe. `probe()` on the adapter answers "is the
board reachable *right now*?"; this module answers "does scraping survive at
personal scale?" from the *persisted* rows (`runs`, `source_request_log`,
`sources`). Conflating the two is the failure this split exists to prevent.

Four rules are load-bearing:

* **Every boundary is configuration.** Not one numeric threshold appears below as
  a literal — each is read from `Settings` via `thresholds()`, so the verdict
  document cites the same names the code reads and Phase 8 can re-evaluate the
  condition by code rather than by re-reading prose (PLAT-04).
* **No absolute target for any field.** Every judgement is a *delta* against the
  recorded baseline or a trailing average. There is deliberately no salary
  fill-rate target: JobSpy's description-salary extraction is USA-only, so an
  Irish search is structurally low and a target would fail forever
  (RESEARCH §S2, Verified Contract 2.5).
* **Pure functions over rows.** Each signal takes plain in-memory input, so its
  boundary is testable with no database and no network. `record_baseline` is the
  single, explicitly-marked I/O edge.
* **Thin evidence is not a measurement.** A signal returns `skip` when it is not
  yet armed (too few runs), which is what makes an honest PROVISIONAL verdict
  possible instead of a verdict fabricated from one run.

This module must never import `jobspy` (it imports `classify_response` from
`app.sources.base`, not from the transport) so the probe lane stays loadable
without the scraper's native toolchain.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Source
from app.sources._jobspy_mapping import DESIRED_ORDER
from app.sources.base import classify_response

SignalStatus = Literal["pass", "warn", "fail", "skip"]

#: The canonical fields whose fill-rate is reported (RESEARCH §S2).
FILL_RATE_FIELDS: tuple[str, ...] = (
    "title",
    "company_name",
    "location_raw",
    "description",
    "posted_at",
    "salary_min",
    "salary_max",
    "source_listing_id",
    "direct_url",
)

FETCH_STATUSES: tuple[str, ...] = ("ok", "partial", "blocked", "rate_limited", "error")

#: The fields P-2 judges: the structural anchors a dedup/queue story depends on.
P2_FIELDS: tuple[str, ...] = ("title", "company_name", "location_raw")

#: Statuses that mean "the board pushed back" rather than "the board was empty".
BLOCKED_STATUSES: frozenset[str] = frozenset({"blocked", "rate_limited"})


# --- results ------------------------------------------------------------------


@dataclass(frozen=True)
class SignalResult:
    """One signal's outcome against its named, configured threshold."""

    signal: str
    name: str
    status: SignalStatus
    observed: float | int | str | None = None
    threshold_name: str | None = None
    threshold_value: float | int | str | None = None
    detail: str = ""

    @property
    def fired(self) -> bool:
        return self.status in ("warn", "fail")


@dataclass(frozen=True)
class FillRateBaseline:
    """The recorded per-field fill-rate anchor for one source (S2)."""

    source: str
    rates: Mapping[str, float]
    recorded_at: datetime | None = None


@dataclass(frozen=True)
class Thresholds:
    """A snapshot of the configured boundaries, read per call (PLAT-04)."""

    fill_warn_points: int
    fill_fail_points: int
    count_warn_pct: int
    count_fail_pct: int
    trailing_runs: int
    freshness_fail_runs: int
    min_runs_before_arming: int
    promotion_window_runs: int
    promotion_blocked_runs: int
    promotion_consecutive_runs: int


def thresholds() -> Thresholds:
    """Read every boundary from `Settings` on each call — never from a literal."""
    return Thresholds(
        fill_warn_points=settings.probe_fill_rate_warn_drop_points,
        fill_fail_points=settings.probe_fill_rate_fail_drop_points,
        count_warn_pct=settings.probe_count_warn_drop_pct,
        count_fail_pct=settings.probe_count_fail_drop_pct,
        trailing_runs=settings.probe_count_trailing_runs,
        freshness_fail_runs=settings.probe_freshness_fail_runs,
        min_runs_before_arming=settings.probe_min_runs_before_arming,
        promotion_window_runs=settings.probe_promotion_window_runs,
        promotion_blocked_runs=settings.probe_promotion_blocked_runs,
        promotion_consecutive_runs=settings.probe_promotion_consecutive_runs,
    )


# --- S1: status outcome distribution -----------------------------------------


def compute_status_distribution(statuses: Sequence[str]) -> dict[str, int]:
    """S1 — the per-source `FetchResult.status` outcome distribution."""
    counts = {status: 0 for status in FETCH_STATUSES}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return counts


def status_distribution_signal(statuses: Sequence[str]) -> SignalResult:
    """S1 as a `SignalResult`. The actionable boundary on it is P-1's."""
    limits = thresholds()
    counts = compute_status_distribution(statuses)
    blocked = counts["blocked"] + counts["rate_limited"]
    observed = f"{blocked}/{len(statuses)} blocked or rate-limited"
    detail = " ".join(f"{name}={counts[name]}" for name in FETCH_STATUSES)
    if not statuses:
        return SignalResult(
            "S1", "status distribution", "skip", observed, detail="no runs recorded"
        )
    return SignalResult(
        "S1",
        "status distribution",
        "pass" if blocked == 0 else "warn",
        observed,
        "probe_promotion_blocked_runs",
        limits.promotion_blocked_runs,
        detail=detail,
    )


# --- S2: fill-rate vs the recorded baseline ----------------------------------


def is_populated(value: Any) -> bool:
    """A blank string is empty, not populated — the S2 contract on records."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def fill_rate_record(**fields: Any) -> dict[str, Any]:
    """Build the mapping `compute_fill_rates` expects from canonical field values."""
    return {name: fields.get(name) for name in FILL_RATE_FIELDS}


def fill_rate_record_from_raw(listing: Any) -> dict[str, Any]:
    """The same mapping from a `RawListing` (or any object with those attributes)."""
    return fill_rate_record(
        title=getattr(listing, "title", None),
        company_name=getattr(listing, "company_name", None),
        location_raw=getattr(listing, "location_raw", None),
        description=getattr(listing, "description", None),
        posted_at=getattr(listing, "posted_at", None),
        salary_min=getattr(listing, "salary_min", None),
        salary_max=getattr(listing, "salary_max", None),
        source_listing_id=getattr(listing, "source_listing_id", None),
        direct_url=getattr(listing, "direct_url", None),
    )


def compute_fill_rates(records: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """S2's input — populated/total per canonical field over ONE run's records.

    The records are the *normalised* ones (post-sanitise), so an all-blank
    description counts as empty rather than as a non-null string.
    """
    total = len(records)
    if total == 0:
        return {name: 0.0 for name in FILL_RATE_FIELDS}
    return {
        name: sum(1 for record in records if is_populated(record.get(name))) / total
        for name in FILL_RATE_FIELDS
    }


def compare_fill_rate(
    field_name: str,
    current: Mapping[str, float],
    reference: Mapping[str, float],
) -> SignalResult:
    """S2 for one field: the drop in percentage points against the reference.

    The reference is the recorded baseline (or the rolling average when no
    baseline exists) — never an assumed target.
    """
    limits = thresholds()
    if field_name not in reference:
        return SignalResult(
            "S2",
            f"fill-rate {field_name}",
            "skip",
            None,
            "probe_fill_rate_warn_drop_points",
            limits.fill_warn_points,
            detail="no baseline recorded for this field",
        )

    current_rate = current.get(field_name, 0.0)
    drop_points = (reference[field_name] - current_rate) * 100.0
    observed = round(drop_points, 2)
    detail = (
        f"{field_name}: {current_rate:.3f} now vs {reference[field_name]:.3f} reference "
        f"({observed:+.1f} points)"
    )

    if drop_points >= limits.fill_fail_points:
        return SignalResult(
            "S2",
            f"fill-rate {field_name}",
            "fail",
            observed,
            "probe_fill_rate_fail_drop_points",
            limits.fill_fail_points,
            detail=detail,
        )
    if drop_points >= limits.fill_warn_points:
        return SignalResult(
            "S2",
            f"fill-rate {field_name}",
            "warn",
            observed,
            "probe_fill_rate_warn_drop_points",
            limits.fill_warn_points,
            detail=detail,
        )
    return SignalResult(
        "S2",
        f"fill-rate {field_name}",
        "pass",
        observed,
        "probe_fill_rate_warn_drop_points",
        limits.fill_warn_points,
        detail=detail,
    )


def fill_rate_signals(
    current: Mapping[str, float], reference: Mapping[str, float]
) -> list[SignalResult]:
    """S2 across every canonical field, ordered by severity then field name."""
    order = {"fail": 0, "warn": 1, "pass": 2, "skip": 3}
    results = [compare_fill_rate(name, current, reference) for name in FILL_RATE_FIELDS]
    return sorted(results, key=lambda result: (order[result.status], result.name))


def worst_fill_rate_signal(
    current: Mapping[str, float], reference: Mapping[str, float]
) -> SignalResult:
    """S2 collapsed to its most severe field, with the other firers named."""
    results = fill_rate_signals(current, reference)
    worst = results[0]
    others = [result.name for result in results[1:] if result.fired]
    if not others:
        return worst
    return SignalResult(
        worst.signal,
        worst.name,
        worst.status,
        worst.observed,
        worst.threshold_name,
        worst.threshold_value,
        detail=f"{worst.detail}; also firing: {', '.join(others)}",
    )


# --- S3: output-count delta vs the trailing mean ------------------------------


def compute_count_delta(
    counts: Sequence[int], *, reference_counts: Sequence[int] | None = None
) -> SignalResult:
    """S3 — the current run's output count against the trailing mean.

    `counts` is oldest-to-newest with the current run last; the trailing mean is
    taken over the `probe_count_trailing_runs` runs before it. Below
    `probe_min_runs_before_arming` prior runs the signal is `skip`: a delta from
    one prior run is a guess, not a baseline (RESEARCH §S3).
    """
    limits = thresholds()
    current = int(counts[-1]) if counts else 0
    prior = list(reference_counts if reference_counts is not None else list(counts)[:-1])
    trailing = prior[-limits.trailing_runs :] if limits.trailing_runs > 0 else []

    if len(trailing) < limits.min_runs_before_arming:
        return SignalResult(
            "S3",
            "output count delta",
            "skip",
            None,
            "probe_min_runs_before_arming",
            limits.min_runs_before_arming,
            detail=f"{len(trailing)} prior run(s) recorded; not armed",
        )

    mean = sum(trailing) / len(trailing)
    if mean <= 0:
        return SignalResult(
            "S3",
            "output count delta",
            "skip",
            None,
            "probe_min_runs_before_arming",
            limits.min_runs_before_arming,
            detail="trailing mean is zero; nothing to compare against",
        )

    delta_pct = (current - mean) / mean * 100.0
    observed = round(delta_pct, 2)
    detail = f"{current} now vs trailing mean {mean:.1f} over {len(trailing)} run(s)"

    if delta_pct <= -limits.count_fail_pct:
        return SignalResult(
            "S3",
            "output count delta",
            "fail",
            observed,
            "probe_count_fail_drop_pct",
            limits.count_fail_pct,
            detail=detail,
        )
    if delta_pct <= -limits.count_warn_pct:
        return SignalResult(
            "S3",
            "output count delta",
            "warn",
            observed,
            "probe_count_warn_drop_pct",
            limits.count_warn_pct,
            detail=detail,
        )
    return SignalResult(
        "S3",
        "output count delta",
        "pass",
        observed,
        "probe_count_warn_drop_pct",
        limits.count_warn_pct,
        detail=detail,
    )


# --- S4: freshness ------------------------------------------------------------


def compute_freshness(runs: Sequence[tuple[str, int]]) -> SignalResult:
    """S4 — `ok` and yet nothing new for `probe_freshness_fail_runs` runs.

    `runs` is oldest-to-newest `(FetchResult.status, new_listings_written)`. The
    contradiction between "ok" and "nothing new" *is* the silent-breakage
    signature (RESEARCH §S4).
    """
    limits = thresholds()
    needed = limits.freshness_fail_runs
    if needed <= 0 or len(runs) < needed:
        return SignalResult(
            "S4",
            "freshness",
            "skip",
            len(runs),
            "probe_freshness_fail_runs",
            needed,
            detail=f"{len(runs)} run(s) recorded; need {needed} to judge",
        )

    tail = list(runs)[-needed:]
    stale = sum(1 for status, new in tail if status == "ok" and new == 0)
    observed = f"{stale}/{needed} consecutive ok runs with no new listing"
    return SignalResult(
        "S4",
        "freshness",
        "fail" if stale == needed else "pass",
        observed,
        "probe_freshness_fail_runs",
        needed,
        detail="the board reports ok but has stopped producing",
    )


# --- S5: block vs parse -------------------------------------------------------


def classify_block_vs_parse(
    *,
    status_code: int | None,
    parsed_items: int,
    stop_signal: str | None = None,
    status: str | None = None,
) -> SignalResult:
    """S5 — fetch-side vs parse-side for one request, from its ledger evidence.

    A block page that returns 200 with a plausible body is the case that looks
    healthy and is not: with a stop signal present it classifies as **fetch-side**,
    which is the opposite remediation from a parse-side miss.
    """
    ok, note = classify_response(
        status_code=status_code, parsed_items=parsed_items, stop_signal=stop_signal
    )
    side = "fetch-side" if note.startswith("fetch-side") else "parse-side"
    if status == "error" and stop_signal is None:
        ok, note, side = (
            False,
            f"fetch-side: transport error (FetchResult.status={status!r})",
            "fetch-side",
        )
    elif status in BLOCKED_STATUSES and stop_signal is None:
        ok, note, side = False, f"fetch-side: FetchResult.status={status!r}", "fetch-side"
    return SignalResult(
        "S5",
        "block vs parse",
        "pass" if ok else "warn",
        side,
        None,
        None,
        detail=note,
    )


# --- S6: schema drift ---------------------------------------------------------


def detect_schema_drift(
    returned_columns: Sequence[str], *, expected: Sequence[str] | None = None
) -> SignalResult:
    """S6 — missing expected JobSpy columns, as a set difference.

    The expected contract is the pinned `desired_order` list rather than an
    inferred one, so a JobSpy upgrade that silently reshapes the frame is visible.
    """
    wanted = tuple(DESIRED_ORDER if expected is None else expected)
    missing = sorted(set(wanted) - set(returned_columns))
    if missing:
        return SignalResult(
            "S6",
            "schema drift",
            "warn",
            len(missing),
            "desired_order",
            len(wanted),
            detail=f"missing expected columns: {', '.join(missing)}",
        )
    return SignalResult(
        "S6",
        "schema drift",
        "pass",
        0,
        "desired_order",
        len(wanted),
        detail=f"all {len(wanted)} pinned columns present",
    )


# --- the Adzuna promotion condition (D-04 / P-1..P-5) -------------------------


@dataclass(frozen=True)
class BoardEvidence:
    """One board's persisted evidence, oldest-to-newest, for the condition."""

    source: str
    run_statuses: Sequence[str] = ()
    output_counts: Sequence[int] = ()
    new_listing_counts: Sequence[int] = ()
    fill_rates: Sequence[Mapping[str, float]] = ()
    baseline: Mapping[str, float] | None = None
    probe_statuses: Sequence[str] = ()
    window_days: int = 0

    @property
    def run_count(self) -> int:
        return len(self.run_statuses)

    @property
    def window_label(self) -> str:
        return f"{self.run_count} run(s) over {self.window_days} day(s)"


def _longest_streak(flags: Sequence[bool], *, needed: int) -> int:
    """The longest run of consecutive True values, capped at `needed`."""
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return min(best, needed) if needed > 0 else 0


def adzuna_promotion_condition(evidence: BoardEvidence) -> list[SignalResult]:
    """P-1..P-5 for one board, plus the "keep as hedge" outcome when none fires.

    Each result names the board and the observation window, so the output is a
    decision input rather than decoration. The promote/keep decision itself is
    Phase 8's (D-04); this function only evaluates the recorded condition.
    """
    limits = thresholds()
    results: list[SignalResult] = []
    prefix = f"{evidence.source} over {evidence.window_label}"

    # P-1 — blocked/rate_limited on >= blocked_runs of a full window.
    blocked = sum(1 for status in evidence.run_statuses if status in BLOCKED_STATUSES)
    if evidence.run_count < limits.promotion_window_runs:
        results.append(
            SignalResult(
                "P-1",
                "board blocked or rate-limited",
                "skip",
                blocked,
                "probe_promotion_window_runs",
                limits.promotion_window_runs,
                detail=f"{prefix}: window not full",
            )
        )
    else:
        results.append(
            SignalResult(
                "P-1",
                "board blocked or rate-limited",
                "fail" if blocked >= limits.promotion_blocked_runs else "pass",
                f"{blocked}/{evidence.run_count}",
                "probe_promotion_blocked_runs",
                limits.promotion_blocked_runs,
                detail=f"{prefix}: {blocked} blocked or rate-limited",
            )
        )

    # P-2 — a structural field >= fail drop below baseline, consecutive runs.
    if not evidence.baseline:
        results.append(
            SignalResult(
                "P-2",
                "structural fill-rate collapse",
                "skip",
                None,
                "probe_fill_rate_fail_drop_points",
                limits.fill_fail_points,
                detail=f"{prefix}: no baseline recorded",
            )
        )
    else:
        flags = [
            any(
                (evidence.baseline.get(name, 0.0) - rates.get(name, 0.0)) * 100.0
                >= limits.fill_fail_points
                for name in P2_FIELDS
            )
            for rates in evidence.fill_rates
        ]
        streak = _longest_streak(flags, needed=limits.promotion_consecutive_runs)
        results.append(
            SignalResult(
                "P-2",
                "structural fill-rate collapse",
                "fail"
                if streak >= limits.promotion_consecutive_runs
                else ("pass" if evidence.fill_rates else "skip"),
                f"{streak} consecutive run(s)",
                "probe_promotion_consecutive_runs",
                limits.promotion_consecutive_runs,
                detail=(
                    f"{prefix}: {', '.join(P2_FIELDS)} >= "
                    f"{limits.fill_fail_points} points below baseline for {streak} run(s)"
                ),
            )
        )

    # P-3 — output count at or below the S3 warn boundary, consecutive runs.
    if len(evidence.output_counts) < limits.min_runs_before_arming + 1:
        results.append(
            SignalResult(
                "P-3",
                "output count collapse",
                "skip",
                None,
                "probe_min_runs_before_arming",
                limits.min_runs_before_arming,
                detail=f"{prefix}: not enough runs to arm",
            )
        )
    else:
        counts = list(evidence.output_counts)
        drop_flags: list[bool] = []
        for index in range(1, len(counts)):
            prior = counts[:index][-limits.trailing_runs :]
            if len(prior) < limits.min_runs_before_arming:
                continue
            mean = sum(prior) / len(prior)
            delta_pct = (counts[index] - mean) / mean * 100.0 if mean > 0 else 0.0
            drop_flags.append(delta_pct <= -limits.count_warn_pct)
        streak = _longest_streak(drop_flags, needed=limits.promotion_consecutive_runs)
        results.append(
            SignalResult(
                "P-3",
                "output count collapse",
                "fail"
                if streak >= limits.promotion_consecutive_runs
                else "pass",
                f"{streak} consecutive run(s)",
                "probe_count_warn_drop_pct",
                limits.count_warn_pct,
                detail=(
                    f"{prefix}: count >= {limits.count_warn_pct}% below the trailing "
                    f"average for {streak} consecutive run(s)"
                ),
            )
        )

    # P-4 — probe() unreachable on consecutive days.
    unreachable_flags = [status == "unreachable" for status in evidence.probe_statuses]
    streak = _longest_streak(unreachable_flags, needed=limits.promotion_consecutive_runs)
    results.append(
        SignalResult(
            "P-4",
            "probe unreachable",
            "fail"
            if streak >= limits.promotion_consecutive_runs
            else ("pass" if evidence.probe_statuses else "skip"),
            f"{streak} consecutive day(s)",
            "probe_promotion_consecutive_runs",
            limits.promotion_consecutive_runs,
            detail=f"{prefix}: probe() unreachable for {streak} consecutive check(s)",
        )
    )

    # P-5 — the S4 contradiction: ok with zero new listings, consecutive runs.
    freshness = compute_freshness(
        list(zip(evidence.run_statuses, evidence.new_listing_counts, strict=False))
    )
    results.append(
        SignalResult(
            "P-5",
            "ok but nothing new",
            "fail"
            if freshness.status == "fail"
            else ("skip" if freshness.status == "skip" else "pass"),
            freshness.observed,
            "probe_freshness_fail_runs",
            limits.freshness_fail_runs,
            detail=f"{prefix}: {freshness.detail}",
        )
    )

    if not any(result.status == "fail" for result in results):
        results.append(
            SignalResult(
                "P-keep",
                "keep Adzuna as hedge",
                "pass",
                None,
                None,
                None,
                detail=(
                    f"{prefix}: no promotion condition fired — the board is inside the "
                    "documented envelope, so Adzuna stays a hedge and the decision is "
                    "Phase 8's"
                ),
            )
        )

    return results


# --- the one I/O edge: the baseline anchor ------------------------------------


async def record_baseline(
    session: AsyncSession,
    *,
    source: str,
    fill_rates: Mapping[str, float],
    now: datetime | None = None,
) -> bool:
    """Record the fill-rate baseline on the FIRST successful run per source.

    Never overwrites: the baseline is the anchor a later run is compared against,
    so re-recording it on every run would erase the very drift S2 exists to
    detect. Returns `False` when the row is absent or a baseline already exists.
    """
    row = await session.scalar(select(Source).where(Source.name == source))
    if row is None:
        return False
    if row.field_fill_baseline_json:
        return False

    row.field_fill_baseline_json = dict(fill_rates)
    row.baseline_recorded_at = now or datetime.now(UTC)
    await session.flush()
    return True


def baseline_from_row(row: Any) -> FillRateBaseline | None:
    """Read the recorded baseline off a `sources` row."""
    rates = getattr(row, "field_fill_baseline_json", None)
    if not isinstance(rates, Mapping):
        return None
    return FillRateBaseline(
        source=str(getattr(row, "name", "")),
        rates={str(name): float(value) for name, value in rates.items()},
        recorded_at=getattr(row, "baseline_recorded_at", None),
    )


__all__ = [
    "BLOCKED_STATUSES",
    "FILL_RATE_FIELDS",
    "P2_FIELDS",
    "BoardEvidence",
    "FillRateBaseline",
    "SignalResult",
    "SignalStatus",
    "Thresholds",
    "adzuna_promotion_condition",
    "baseline_from_row",
    "classify_block_vs_parse",
    "compare_fill_rate",
    "compute_count_delta",
    "compute_fill_rates",
    "compute_freshness",
    "compute_status_distribution",
    "detect_schema_drift",
    "fill_rate_record",
    "fill_rate_record_from_raw",
    "fill_rate_signals",
    "is_populated",
    "record_baseline",
    "status_distribution_signal",
    "thresholds",
    "worst_fill_rate_signal",
]
