"""SRC-02 / SRC-03 — the Indeed adapter and the Ireland country guard.

Fixture-driven, no network. The `country_indeed` guard is the specific defence
against the failure mode that looks like success: JobSpy defaults to `"usa"` and
returns perfectly parseable US listings (RESEARCH Pitfall 6).
"""

from __future__ import annotations

import dataclasses
import json
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from app.sources import indeed as indeed_module
from app.sources._jobspy_mapping import map_jobspy_row
from app.sources.base import FetchBudget, RawListing, SearchQuery
from app.sources.indeed import CAPABILITIES, IndeedAdapter
from app.sources.linkedin import LinkedInAdapter
from app.sources.linkedin import map_jobspy_row as map_linkedin_row

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


def _fake_httpx(
    *,
    status_code: int = 200,
    body: str = "",
    error: BaseException | None = None,
) -> types.SimpleNamespace:
    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def get(self, url: str) -> Any:
            if error is not None:
                raise error
            return types.SimpleNamespace(status_code=status_code, text=body)

    return types.SimpleNamespace(AsyncClient=FakeClient)


# --- same shape as LinkedIn ---------------------------------------------------
def test_indeed_maps_into_the_same_normalised_shape_as_linkedin() -> None:
    indeed_raw = _load("indeed_page1.json")[0]
    linkedin_raw = _load("linkedin_page1.json")[0]

    from_indeed = map_jobspy_row(indeed_raw, source="indeed")
    from_linkedin = map_linkedin_row(linkedin_raw, source="linkedin")

    assert dataclasses.is_dataclass(from_indeed)
    assert type(from_indeed) is type(from_linkedin) is RawListing

    # One shape: identical field sets, so no board-specific field leaked in.
    assert set(dataclasses.asdict(from_indeed)) == set(dataclasses.asdict(from_linkedin))

    # The same job on both boards normalises to the same values for every field
    # both boards supply. (Salary and the raw location string legitimately differ:
    # Indeed carries structured compensation and formats its location differently.)
    for field in ("title", "company_name", "job_type", "posted_at", "is_remote"):
        assert getattr(from_indeed, field) == getattr(from_linkedin, field), field
    assert from_indeed.location_raw and from_linkedin.location_raw
    assert from_indeed.source == "indeed"
    assert from_linkedin.source == "linkedin"


async def test_indeed_adapter_maps_fixture_items() -> None:
    transport = FakeTransport(rows=_load("indeed_page1.json"))
    adapter = IndeedAdapter(transport=transport)

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "ok"
    assert result.source == "indeed"
    assert [item.title for item in result.items] == [
        "Senior Python Engineer",
        "Platform Engineer",
    ]
    assert result.items[0].source_listing_id == "1a2b3c4d5e6f7890"
    assert result.items[0].salary_min == 70000
    assert result.items[0].salary_currency == "EUR"
    assert transport.calls[0]["kwargs"]["site_name"] == "indeed"


# --- the Ireland guard --------------------------------------------------------
def test_country_indeed_is_pinned_to_ireland() -> None:
    adapter = IndeedAdapter(transport=FakeTransport())

    kwargs = adapter.build_kwargs(SearchQuery(keywords="python"), _budget())

    assert "country_indeed" in kwargs, "the parameter must never be left unset"
    assert kwargs["country_indeed"] == "ireland"


def test_country_indeed_guard_rejects_the_library_default() -> None:
    adapter = IndeedAdapter(transport=FakeTransport())

    kwargs = adapter.build_kwargs(SearchQuery(keywords="python"), _budget())

    # JobSpy's default is "usa"; anything but Ireland silently poisons the corpus.
    assert kwargs["country_indeed"] != "usa"
    assert kwargs["country_indeed"] in {"ireland", "ie"}


def test_country_indeed_is_sourced_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = IndeedAdapter(transport=FakeTransport())
    monkeypatch.setattr(settings, "probe_country_indeed", "spain")

    kwargs = adapter.build_kwargs(SearchQuery(keywords="python"), _budget())

    # Reading settings (rather than a literal) is what PLAT-04 requires.
    assert kwargs["country_indeed"] == "spain"


# --- totality (R1) ------------------------------------------------------------
async def test_missing_id_fixture_yields_none() -> None:
    adapter = IndeedAdapter(transport=FakeTransport(rows=_load("indeed_missing_id.json")))

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert isinstance(result.items[0], RawListing)
    assert result.items[0].source_listing_id is None
    assert result.items[0].title == "Backend Engineer"


async def test_transport_failure_returns_an_error_result_and_never_raises() -> None:
    adapter = IndeedAdapter(transport=FakeTransport(error=RuntimeError("boom")))

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "error"
    assert result.items == []
    assert "boom" in (result.error or "")


async def test_rate_limit_is_classified() -> None:
    adapter = IndeedAdapter(
        transport=FakeTransport(error=RuntimeError("HTTP 429 too many requests"))
    )

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "rate_limited"


async def test_fetch_refuses_before_the_call_when_the_budget_is_exhausted() -> None:
    transport = FakeTransport(rows=_load("indeed_page1.json"), allow=False)
    adapter = IndeedAdapter(transport=transport)

    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert result.status == "error"
    assert transport.calls == [], "the pre-call budget check must prevent the scrape"


# --- PII ----------------------------------------------------------------------
async def test_email_canary_never_reaches_the_domain_object() -> None:
    row = _load("indeed_page1.json")[0]
    assert row["emails"], "fixture must carry a value in the library's email column"

    adapter = IndeedAdapter(transport=FakeTransport(rows=[row]))
    result = await adapter.fetch(SearchQuery(keywords="engineer"), _budget())

    assert CANARY not in repr(result.items)
    assert "emails" not in {field.name for field in dataclasses.fields(RawListing)}


# --- capabilities -------------------------------------------------------------
def test_indeed_capabilities_do_not_carry_linkedin_exclusivity() -> None:
    assert CAPABILITIES.exclusive_filter_groups == ()
    assert LinkedInAdapter.capabilities.exclusive_filter_groups != ()
    assert CAPABILITIES.supports_full_description_in_search is True
    assert CAPABILITIES.requires_second_pass_for_description is False


# --- probe --------------------------------------------------------------------
async def test_probe_returns_ok_on_a_healthy_known_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        indeed_module, "httpx", _fake_httpx(status_code=200, body="job listing " * 400)
    )

    assert await IndeedAdapter(transport=FakeTransport()).probe() == "ok"


async def test_probe_returns_degraded_on_a_block_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        indeed_module, "httpx", _fake_httpx(status_code=200, body="solve this captcha " * 200)
    )

    assert await IndeedAdapter(transport=FakeTransport()).probe() == "degraded"


async def test_probe_returns_degraded_on_a_short_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indeed_module, "httpx", _fake_httpx(status_code=200, body="tiny"))

    assert await IndeedAdapter(transport=FakeTransport()).probe() == "degraded"


async def test_probe_returns_unreachable_on_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        indeed_module, "httpx", _fake_httpx(error=RuntimeError("connection reset"))
    )

    assert await IndeedAdapter(transport=FakeTransport()).probe() == "unreachable"


async def test_probe_returns_unreachable_on_a_non_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        indeed_module, "httpx", _fake_httpx(status_code=503, body="job listing " * 400)
    )

    assert await IndeedAdapter(transport=FakeTransport()).probe() == "unreachable"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])


# --- the no-credential prohibition --------------------------------------------
CREDENTIAL_KEY_HINTS = (
    "password",
    "username",
    "token",
    "cookie",
    "cookies",
    "session",
    "credential",
    "login",
    "api_key",
)


def test_country_indeed_is_passed_on_every_fetch_call() -> None:
    """Not just built — actually handed to the transport on the call."""
    import asyncio

    transport = FakeTransport(rows=_load("indeed_page1.json"))
    adapter = IndeedAdapter(transport=transport)

    asyncio.run(adapter.fetch(SearchQuery(keywords="engineer"), _budget()))

    assert transport.calls, "the transport must have been called"
    assert transport.calls[0]["site"] == "indeed"
    assert transport.calls[0]["kwargs"]["country_indeed"] == "ireland"


def test_both_adapters_build_no_credential_bearing_kwargs() -> None:
    from app.sources.linkedin import LinkedInAdapter

    adapters = (
        IndeedAdapter(transport=FakeTransport()),
        LinkedInAdapter(transport=FakeTransport()),
    )
    for adapter in adapters:
        kwargs = adapter.build_kwargs(SearchQuery(keywords="x"), _budget())
        keys = {key.casefold() for key in kwargs}
        offenders = [
            key for key in keys if any(hint in key for hint in CREDENTIAL_KEY_HINTS)
        ]
        assert offenders == [], f"{adapter.name} builds a credential kwarg: {offenders}"


def test_no_credential_material_anywhere_in_the_sources_package() -> None:
    sources_dir = Path(indeed_module.__file__).resolve().parent
    offenders: dict[str, list[str]] = {}
    tokens = ("JOBSPY_CREDS", "LINKEDIN_USERNAME", "LINKEDIN_PASSWORD", "INDEED_EMAIL", "cookies=")

    for path in sorted(sources_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        found = [token for token in tokens if token.casefold() in text.casefold()]
        if found:
            offenders[path.name] = found

    assert offenders == {}, (
        f"a credentialed acquisition path reappeared: {offenders}"
    )
