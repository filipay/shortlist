"""Pure domain types.

`User` is the type the auth seam returns. `NormalisedListing` is the canonical,
board-agnostic listing produced by the normalise stage; `ListingSourceRef` is the
per-source reference used to key the Tier-1 upsert.

This module imports no I/O — enforced by `tests/test_import_discipline.py` (D-24).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class User:
    """A user of the tool. `email` is optional because no auth exists in v1."""

    id: str
    name: str
    email: str | None = None


@dataclass(frozen=True)
class ListingSourceRef:
    """Where one board's observation of a listing came from."""

    source: str
    source_listing_id: str | None
    source_url: str
    canonical_source_url: str
    direct_url: str | None = None
    raw_hash: str | None = None


@dataclass(frozen=True)
class NormalisedListing:
    """The canonical shape one board's raw observation collapses into.

    Both Tier-1 dedup keys derive from this: `source_listing_id` (nullable, key A)
    and `canonical_source_url`/`canonical_url` (key B).
    """

    canonical_url: str
    source: str
    source_listing_id: str | None
    title: str
    title_norm: str
    company_name: str | None
    company_norm: str | None
    location_raw: str | None
    location_norm: str | None
    description: str | None
    content_hash: str
    salary_min: float | None = None
    salary_max: float | None = None
    salary_interval: str | None = None
    salary_currency: str | None = None
    salary_source: str | None = None
    posted_at: date | None = None
    is_remote: bool | None = None
    source_url: str | None = None
    canonical_source_url: str | None = None
    direct_url: str | None = None
    city: str | None = None
    region: str | None = None
    country_code: str | None = None
    seniority: str | None = None
    apply_url: str | None = None
    description_hash: str | None = None
    raw_hash: str | None = None
    blocking_key: str | None = None
    source_extras: dict = field(default_factory=dict)
    #: A counts-only finding about instruction-like text in this listing (§6.3).
    #: Deliberately tiny — `{"instruction_like": bool, "patterns_matched": int}` —
    #: so the sanitize module's counts-only invariant (no matched text, no excerpt,
    #: no position) is preserved by the TYPE itself: there is no field here able to
    #: carry prose. `None` means "no signal", which is what keeps `listing_repo`'s
    #: `if value is not None` guard from clobbering a previously recorded finding.
    quality_signals: dict | None = None

    @property
    def remote_flag(self) -> bool | None:
        """The DB column name for `is_remote`."""
        return self.is_remote

    @property
    def source_extras_json(self) -> dict | None:
        """The DB column name for `source_extras`."""
        return self.source_extras or None

    @property
    def quality_signals_json(self) -> dict | None:
        """The DB column name for `quality_signals` — `None` when there is no signal."""
        return self.quality_signals or None


__all__ = ["ListingSourceRef", "NormalisedListing", "User"]
