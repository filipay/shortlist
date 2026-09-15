"""The shared JobSpy row mapper — one normalisation shape for every board.

Both adapters reuse this so a listing is the same shape whichever board produced
it (SRC-03). It is deliberately board-agnostic: it reads only the pinned
`desired_order` columns and puts board-specific columns into `source_extras`.

**The `emails` column is never read.** JobSpy extracts recruiter addresses into it
and a `RawListing` has no field to hold one — PII is unrepresentable, not
filtered (R2 / T-01-12 / T-01-20).

This module must never import `jobspy` (or any I/O): it is a pure row transform,
and keeping it dependency-free is what lets the unit tests exercise it without the
scraper's native toolchain.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.sources.base import RawListing

#: The pinned JobSpy column contract. A *missing* expected column is schema
#: drift (signal S6), so the set is versioned here rather than inferred.
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

#: Board fields that do not deserve a core column (R6). A board that does not
#: populate one simply contributes nothing.
EXTRA_FIELDS = ("job_level", "job_function", "listing_type", "company_industry")

#: Columns that must NEVER be mapped. Read into no variable, present on no
#: dataclass, stored in no column.
DROP_FIELDS = ("emails",)


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


def map_jobspy_row(row: Any, *, source: str) -> RawListing:
    """Map one JobSpy row (dict or pandas Series) to a `RawListing`.

    Reads only the pinned `desired_order` fields. The `emails` column is in
    `DROP_FIELDS` and is never read into a variable.
    """
    extras = {
        key: _read(row, key) for key in EXTRA_FIELDS if not _is_missing(_read(row, key))
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


__all__ = ["DESIRED_ORDER", "DROP_FIELDS", "EXTRA_FIELDS", "map_jobspy_row"]
