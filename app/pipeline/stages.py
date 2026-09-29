"""Pipeline stages and their instrumentation (Pattern 6).

Every stage is a callable with a `name` and a counter, and its counts/errors end
up in the `runs` row. "Why is the queue empty?" must be answerable from the
database months later, so the observation is persisted, not just the conclusion.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.domain.listing import (
    annualise_salary,
    blocking_key,
    canonical_url,
    content_hash,
    description_hash,
    normalise_company_name,
    normalise_location,
    normalise_title,
    raw_fingerprint,
)
from app.domain.models import NormalisedListing
from app.sources.base import RawListing

NORMALISE_STAGE = "normalise"

#: Deliberately conservative title heuristic, used ONLY when the board gave no
#: `job_level`. It matches word-boundary tokens so `internal` is not read as
#: `intern`, and it deliberately does NOT include `manager`: tagging a manager role
#: as senior or junior would silently hide a job the user asked to see. Anything
#: unmatched stays `None`, and the seniority filter's default policy is
#: unknown-passes — an unknown must never be excluded.
_JUNIOR_TITLE_RE = re.compile(
    r"\b(?:intern|trainee|graduate|junior)\b|\bentry[\s-]*level\b"
)
_SENIOR_TITLE_RE = re.compile(
    r"\b(?:principal|staff|lead|director|senior|sr)\b"
    r"|\bhead\s+of\b"
    r"|\bvp\b"
    r"|\bvice\s+president\b"
)


def _seniority_from_title(title: str) -> str | None:
    """A conservative level guess from the title, or `None` when it is not obvious."""
    lowered = title.casefold()
    if _JUNIOR_TITLE_RE.search(lowered):
        return "junior"
    if _SENIOR_TITLE_RE.search(lowered):
        return "senior"
    return None


@dataclass
class StageCounts:
    """Per-stage counters that are written into `runs.source_counts_json`."""

    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def bump(self, key: str, amount: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + amount

    def fail(self, message: str) -> None:
        self.errors.append(message)


@dataclass(frozen=True)
class StageResult:
    name: str
    counts: dict[str, int]
    errors: list[str]


@runtime_checkable
class Stage(Protocol):
    """A named pipeline step that records what it did."""

    name: str

    async def run(self, payload: object) -> StageResult: ...


def normalise_listing(
    raw: RawListing, *, quality_signals: Mapping[str, Any] | None = None
) -> NormalisedListing:
    """Board-shaped `RawListing` -> canonical `NormalisedListing`.

    Pure: one function, no I/O, so both dedup keys are unit-testable without a
    database or a network (Pattern 2).

    `quality_signals` is a counts-only finding (§6.3) and arrives as an ARGUMENT
    precisely so this function stays pure — the caller owns the sanitize report.
    An empty or absent mapping both become `None`, never `{}`: `listing_repo`'s
    `if value is not None` guard is what stops a clean listing clobbering a
    previously recorded signal.
    """
    canonical = canonical_url(raw.source_url, raw.direct_url)
    company_norm = normalise_company_name(raw.company_name)
    title_norm = normalise_title(raw.title)
    location_norm = normalise_location(raw.location_raw)

    salary_min, salary_max, interval, currency = annualise_salary(
        raw.salary_min, raw.salary_max, raw.salary_interval, raw.salary_currency
    )

    # The board's own level wins; only when it gave nothing do we fall back to the
    # conservative title heuristic (which itself may return `None`).
    seniority = raw.seniority or _seniority_from_title(raw.title)

    return NormalisedListing(
        canonical_url=canonical,
        source=raw.source,
        source_listing_id=raw.source_listing_id,
        title=raw.title,
        title_norm=title_norm,
        company_name=raw.company_name,
        company_norm=company_norm,
        location_raw=raw.location_raw,
        location_norm=location_norm,
        description=raw.description,
        content_hash=content_hash(
            title=raw.title,
            company_name=raw.company_name,
            location_raw=raw.location_raw,
            description=raw.description,
        ),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_interval=interval,
        salary_currency=currency,
        salary_source=raw.salary_source,
        posted_at=raw.posted_at,
        is_remote=raw.is_remote,
        seniority=seniority,
        source_url=raw.source_url,
        canonical_source_url=canonical,
        direct_url=raw.direct_url,
        apply_url=raw.direct_url or raw.source_url or None,
        description_hash=description_hash(raw.description),
        raw_hash=raw_fingerprint(
            source=raw.source,
            source_listing_id=raw.source_listing_id,
            source_url=raw.source_url,
            title=raw.title,
            company_name=raw.company_name,
            location_raw=raw.location_raw,
            description=raw.description,
        ),
        blocking_key=blocking_key(company_norm, title_norm),
        source_extras=dict(raw.source_extras or {}),
        quality_signals=dict(quality_signals) if quality_signals else None,
    )


class NormaliseStage:
    """The `normalise` stage: one `RawListing` in, one `NormalisedListing` out."""

    name = NORMALISE_STAGE

    async def run(self, payload: RawListing) -> StageResult:  # type: ignore[override]
        raise NotImplementedError(
            "NormaliseStage is a named marker; call normalise_listing() directly."
        )


__all__ = [
    "NORMALISE_STAGE",
    "NormaliseStage",
    "Stage",
    "StageCounts",
    "StageResult",
    "normalise_listing",
]
