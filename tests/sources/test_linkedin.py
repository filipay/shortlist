"""SRC-01 — the LinkedIn adapter over the shared transport. Fixture-driven, no network."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.sources import registry
from app.sources.base import FetchBudget, RawListing, SearchQuery
from app.sources.linkedin import LinkedInAdapter, map_jobspy_row

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "listings"
CANARY = "PII-CANARY-EMAIL-VALUE"


def _load(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _budget(**overrides: Any) -> FetchBudget:
    base: dict[str, Any] = {
        "max_requests": 2,
        "max_results": 50,
        "max_detail_fetches": 0,
        "deadline": datetime.now(UTC) + timedelta(seconds=60),
    }
    base.update(overrides)
    return FetchBudget(**base)


class FakeTransport:
    """Stands in for `_jobspy_transport` so unit tests never import jobspy."""

    def __init__(
        self,
        rows: list[Any] | None = None,
        error: BaseException | None = None,
        allow: bool = True,
    ) -> None:
        self.rows = rows if rows is not None else []
        self.error = error
        self.allow = allow
        self.calls: list[dict[str, Any]] = []

    def budget_allows(self, budget: FetchBudget, *, source: str, requests_needed: int) -> bool:
        return self.allow

    async def run_scrape(self, *, site: str, kwargs: dict, deadline_s: float) -> list[Any]:
        self.calls.append({"site": site, "kwargs": kwargs, "deadline_s": deadline_s})
        if self.error is not None:
            raise self.error
        return self.rows


# --- mapping ------------------------------------------------------------------
def test_maps_fixture_row_to_raw_listing() -> None:
    row = _load("linkedin_page1.json")[0]

    listing = map_jobspy_row(row)

    assert listing.source == "linkedin"
    assert listing.source_listing_id == "3928174653"
    assert listing.title == "Senior Python Engineer"
    assert listing.company_name == "Acme"
    assert listing.location_raw == "Dublin, County Dublin, Ireland"
    assert listing.source_url.startswith("https://ie.linkedin.com/jobs/view/")
    assert listing.direct_url == "https://acme.example.com/careers/senior-python-engineer"
    assert listing.is_remote is False
    assert listing.posted_at is not None
    assert listing.job_type == ("fulltime",)


def test_missing_id_fixture_yields_none_without_raising() -> None:
    row = _load("linkedin_missing_id.json")[0]

    listing = map_jobspy_row(row)

    assert isinstance(listing, RawListing)
    assert listing.source_listing_id is None
    assert listing.title == "Backend Engineer"


def test_empty_description_is_deterministic() -> None:
    row = _load("linkedin_empty_description.json")[0]

    first = map_jobspy_row(row)
    second = map_jobspy_row(row)

    assert first.description is None
    assert first.description == second.description


def test_source_extras_carries_board_specific_fields() -> None:
    listing = map_jobspy_row(_load("linkedin_page1.json")[0])

    assert listing.source_extras["job_level"] == "Mid-Senior level"
    assert listing.source_extras["job_function"] == "Engineering"
    assert listing.source_extras["listing_type"] == "full-time"
    # Nothing board-specific leaked into a core field.
    assert not hasattr(listing, "job_level")


def test_email_column_is_never_mapped() -> None:
    row = _load("linkedin_page1.json")[0]
    assert row["emails"], "fixture must carry a value in the library's email column"

    listing = map_jobspy_row(row)

    field_names = {field.name for field in dataclasses.fields(RawListing)}
    assert "emails" not in field_names
    assert "email" not in field_names
    assert CANARY not in repr(listing)
    assert CANARY not in repr(listing.source_extras)


# --- kwargs / budget ----------------------------------------------------------
def test_build_kwargs_targets_linkedin_and_respects_the_budget() -> None:
    adapter = LinkedInAdapter(transport=FakeTransport())

    kwargs = adapter.build_kwargs(
        SearchQuery(keywords="python engineer", location="Dublin", results_wanted=500),
        _budget(max_results=50),
    )

    assert kwargs["site_name"] == "linkedin"
    assert kwargs["search_term"] == "python engineer"
    assert kwargs["location"] == "Dublin"
    assert kwargs["results_wanted"] == 50
    # The O(n) detail pass stays off in Phase 1 (R4).
    assert kwargs["linkedin_fetch_description"] is False


async def test_fetch_returns_mapped_items() -> None:
    rows = _load("linkedin_page1.json")
    transport = FakeTransport(rows=rows)
    adapter = LinkedInAdapter(transport=transport)

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "ok"
    assert len(result.items) == 2
    assert result.requests_used == 1
    assert transport.calls[0]["site"] == "linkedin"
    assert transport.calls[0]["deadline_s"] > 0


# --- totality (R1) ------------------------------------------------------------
async def test_transport_failure_returns_error_result_and_never_raises() -> None:
    adapter = LinkedInAdapter(transport=FakeTransport(error=RuntimeError("boom")))

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "error"
    assert result.items == []
    assert "boom" in (result.error or "")


async def test_rate_limit_is_classified_as_rate_limited() -> None:
    adapter = LinkedInAdapter(
        transport=FakeTransport(error=RuntimeError("HTTP 429 too many requests"))
    )

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "rate_limited"


async def test_block_is_classified_as_blocked() -> None:
    adapter = LinkedInAdapter(
        transport=FakeTransport(error=RuntimeError("403 Forbidden: captcha"))
    )

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "blocked"


async def test_fetch_refuses_before_the_call_when_the_budget_is_exhausted() -> None:
    transport = FakeTransport(rows=_load("linkedin_page1.json"), allow=False)
    adapter = LinkedInAdapter(transport=transport)

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "error"
    assert transport.calls == [], "the pre-call budget check must prevent the scrape"


async def test_timeout_is_reported_not_raised() -> None:
    adapter = LinkedInAdapter(transport=FakeTransport(error=TimeoutError()))

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "error"
    assert "deadline" in (result.error or "")


# --- capabilities / registry --------------------------------------------------
def test_capabilities_declare_the_linkedin_exclusive_filter_group() -> None:
    capabilities = LinkedInAdapter.capabilities

    assert capabilities.requires_second_pass_for_description is True
    assert frozenset({"hours_old", "easy_apply"}) in capabilities.exclusive_filter_groups


def test_registry_resolves_linkedin_by_name() -> None:
    assert registry.get("linkedin") is LinkedInAdapter


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
