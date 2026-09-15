"""Regression — a real pandas DataFrame must become rows, not column labels.

`list(df)` yields column labels (`"id"`, `"site"`, `"title"`, …), so the old
`rows = list(frame)` produced one empty `RawListing` per column, an identical
`content_hash` for every row, and a whole page collapsed into a single listing. The
JSON fixtures are lists of dicts, so they could never catch it; these tests drive a
real DataFrame through each adapter's `fetch()` with only the transport stubbed.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import pytest

from app.pipeline.stages import normalise_listing
from app.sources._jobspy_mapping import (
    DESIRED_ORDER,
    UnsupportedFrameError,
    _as_tuple,
    frame_rows,
    map_jobspy_row,
)
from app.sources.base import FetchBudget, RawListing, SearchQuery
from app.sources.indeed import IndeedAdapter
from app.sources.linkedin import LinkedInAdapter

CANARY = "PII-CANARY-EMAIL-VALUE"

ADAPTERS = pytest.mark.parametrize(
    "adapter_cls", [LinkedInAdapter, IndeedAdapter], ids=["linkedin", "indeed"]
)


def _budget() -> FetchBudget:
    return FetchBudget(
        max_requests=2,
        max_results=50,
        max_detail_fetches=0,
        deadline=datetime.now(UTC) + timedelta(seconds=60),
    )


def _row(**overrides: Any) -> dict[str, Any]:
    """A full frame row, defaulted to the real (mostly null) flattened shape."""
    base: dict[str, Any] = {column: None for column in DESIRED_ORDER}
    base.update({"site": "linkedin", "is_remote": False, "emails": CANARY})
    base.update(overrides)
    return base


def _frame() -> pd.DataFrame:
    """A real DataFrame laid out in JobSpy's `desired_order`, with distinct rows."""
    rows = [
        _row(
            id="li-1001",
            job_url="https://ie.linkedin.com/jobs/view/1001",
            title="Senior Python Engineer",
            company="Acme",
            location="Dublin, County Dublin, Ireland",
            date_posted="2026-09-01",
            job_type="full-time",
            description="Build the thing.",
        ),
        _row(
            id="li-1002",
            job_url="https://ie.linkedin.com/jobs/view/1002",
            title="Platform Engineer",
            company="Globex",
            location="Cork, County Cork, Ireland",
            date_posted="2026-09-02",
            job_type="full-time, part-time",
            description="Run the platform.",
        ),
    ]
    return pd.DataFrame(rows, columns=list(DESIRED_ORDER))


class DataFrameTransport:
    """Stands in for `_jobspy_transport`, returning a real DataFrame, not a list."""

    def __init__(self, frame: Any) -> None:
        self.frame = frame

    def budget_allows(self, budget: FetchBudget, *, source: str, requests_needed: int) -> bool:
        return True

    async def run_scrape(self, *, site: str, kwargs: dict, deadline_s: float) -> Any:
        return self.frame


@ADAPTERS
async def test_a_dataframe_is_converted_to_mapped_rows(adapter_cls: type) -> None:
    adapter = adapter_cls(transport=DataFrameTransport(_frame()))

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "ok"
    assert [item.title for item in result.items] == [
        "Senior Python Engineer",
        "Platform Engineer",
    ]
    for item in result.items:
        assert item.title, "a DataFrame row must not map to an empty title"
        assert item.company_name, "a DataFrame row must not map to an empty company"
        assert item.location_raw, "a DataFrame row must not map to an empty location"
        assert item.source_listing_id
        assert item.source_url


@ADAPTERS
async def test_distinct_dataframe_rows_do_not_collapse_to_one_content_hash(
    adapter_cls: type,
) -> None:
    adapter = adapter_cls(transport=DataFrameTransport(_frame()))

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    hashes = [normalise_listing(item).content_hash for item in result.items]
    assert len(hashes) == 2
    assert hashes[0] != hashes[1], (
        "distinct rows produced one content_hash — the page collapsed into one listing "
        "(the DataFrame-as-column-labels defect)"
    )


def test_frame_rows_returns_records_for_a_dataframe() -> None:
    rows = frame_rows(_frame())

    assert len(rows) == 2
    assert all(isinstance(row, dict) for row in rows)
    assert {row["title"] for row in rows} == {
        "Senior Python Engineer",
        "Platform Engineer",
    }
    # A column label can never be mistaken for a row.
    assert not any(isinstance(row, str) for row in rows)


def test_frame_rows_passes_through_test_doubles_unchanged() -> None:
    mapping = {"id": "x", "title": "Engineer"}
    assert frame_rows([mapping]) == [mapping]

    series = pd.Series({"id": "y", "title": "Other"})
    out = frame_rows([series])
    assert len(out) == 1
    assert out[0] is series


def test_frame_rows_handles_none_and_empty_frames() -> None:
    assert frame_rows(None) == []
    assert frame_rows(pd.DataFrame()) == []


@pytest.mark.parametrize("bad", ["title", 42, object(), {"title": "Engineer"}])
def test_frame_rows_raises_for_anything_that_is_not_a_frame_or_rows(bad: Any) -> None:
    """No silent-empty path: an unknown type fails loudly instead of yielding []."""
    with pytest.raises(UnsupportedFrameError):
        frame_rows(bad)


def test_job_type_string_splits_into_a_multi_element_tuple() -> None:
    assert _as_tuple("full-time, part-time") == ("full-time", "part-time")
    # Existing behaviour for real collections and bare strings is unchanged.
    assert _as_tuple(["fulltime", "contract"]) == ("fulltime", "contract")
    assert _as_tuple("fulltime") == ("fulltime",)
    assert _as_tuple(None) == ()


def test_the_email_column_is_still_never_read_from_a_dataframe_row() -> None:
    row = frame_rows(_frame())[0]
    assert row["emails"], "the frame must carry a value in the library's email column"

    listing = map_jobspy_row(row, source="linkedin")

    assert CANARY not in repr(listing)
    assert CANARY not in repr(listing.source_extras)
    assert "emails" not in {field.name for field in dataclasses.fields(RawListing)}
