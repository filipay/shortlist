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

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from app.sources.base import RawListing

#: The pinned JobSpy column contract (source: `jobspy/util.py` `desired_order`). A
#: *missing* expected column is schema drift (signal S6), so the set is versioned
#: here rather than inferred — including the naukri tail, which S6 must be able to
#: detect a rename/removal in.
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
    # naukri-specific fields (the `jobspy/util.py` `desired_order` tail)
    "skills",
    "experience_range",
    "company_rating",
    "company_reviews_count",
    "vacancy_count",
    "work_from_home_type",
)

#: Board fields that do not deserve a core column (R6). A board that does not
#: populate one simply contributes nothing.
EXTRA_FIELDS = ("job_level", "job_function", "listing_type", "company_industry")

#: Columns that must NEVER be mapped. Read into no variable, present on no
#: dataclass, stored in no column.
DROP_FIELDS = ("emails",)

#: The naukri tail of `desired_order` (`skills` … `work_from_home_type`) is part of
#: the pinned S6 column contract but is deliberately NOT mapped into a core field
#: or `source_extras`: those fields are board-specific, carry no PII, and no Phase-1
#: consumer needs them. They are listed here so the omission is explicit rather
#: than an accident of the contract's length. Unlike `DROP_FIELDS`, this is not a
#: safety rule — only `emails` is forbidden to read.
UNMAPPED_FIELDS = (
    "skills",
    "experience_range",
    "company_rating",
    "company_reviews_count",
    "vacancy_count",
    "work_from_home_type",
)


class UnsupportedFrameError(TypeError):
    """`run_scrape` returned something that cannot be turned into rows.

    Raised rather than returning `[]`: a silent-empty conversion is exactly what
    turned a full page of scraped jobs into one empty listing.
    """


def frame_rows(frame: Any) -> list[Any]:
    """Turn whatever `run_scrape` returns into mappable rows.

    JobSpy returns a pandas **DataFrame**, and iterating a DataFrame yields its
    *column labels* (`"id"`, `"site"`, `"title"`, …) — not its rows. The old
    `list(frame)` therefore produced one empty `RawListing` per column, an identical
    `content_hash` for every row, and a whole page collapsed into one listing.

    This is the single, explicit conversion point:

    - a DataFrame → ``frame.to_dict(orient="records")``, so each row is a dict keyed
      by column name;
    - an empty/`None` frame → ``[]``;
    - a list/iterable of dicts or pandas Series (the test doubles) → its rows,
      unchanged;
    - anything else → `UnsupportedFrameError`, so the silent-empty path cannot
      return.
    """
    if frame is None:
        return []

    # A DataFrame (or any tabular object) exposes `columns` and `to_dict`. A pandas
    # Series does not have `columns`, so a Series row is never mistaken for a frame.
    if hasattr(frame, "columns") and callable(getattr(frame, "to_dict", None)):
        records = frame.to_dict(orient="records")
        return list(records) if records else []

    if isinstance(frame, (list, tuple)):
        return list(frame)

    # Any other non-string, non-mapping iterable is an iterable of rows.
    if isinstance(frame, Iterable) and not isinstance(frame, (str, bytes, Mapping)):
        return list(frame)

    raise UnsupportedFrameError(
        f"run_scrape returned {type(frame).__name__!r}, which cannot be turned into "
        "job rows; expected a pandas DataFrame or an iterable of row mappings"
    )


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
    # JobSpy flattens `job_type` to a comma-joined string before building the
    # DataFrame (`", ".join(job_type.value[0] ...)`), so split it back into elements.
    text = str(value)
    if ", " in text:
        return tuple(part for part in (token.strip() for token in text.split(", ")) if part)
    return (text,)


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


__all__ = [
    "DESIRED_ORDER",
    "DROP_FIELDS",
    "EXTRA_FIELDS",
    "UNMAPPED_FIELDS",
    "UnsupportedFrameError",
    "frame_rows",
    "map_jobspy_row",
]
