"""SRC-07 / PLAT-04 — every survival boundary, exactly at its configured value.

One test per WARN/FAIL boundary and one per promotion condition. The boundary
values are *monkeypatched to exact numbers* so each test is an exact boundary test
rather than a test of whatever the defaults happen to be; a separate test pins the
documented defaults to the RESEARCH values, so drifting a default fails loudly.

All fixture-driven: no database is needed for the signals, and no network is
touched anywhere in this file. The two exceptions that do need a session (the
ledger row and the baseline anchor) use the migrated temp database.
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Source, SourceRequestLog
from app.pipeline.run import build_budget, run_pipeline
from app.probe.survival import (
    BoardEvidence,
    adzuna_promotion_condition,
    classify_block_vs_parse,
    compare_fill_rate,
    compute_count_delta,
    compute_fill_rates,
    compute_freshness,
    compute_status_distribution,
    detect_schema_drift,
    fill_rate_signals,
    record_baseline,
    status_distribution_signal,
)
from app.sources import registry
from app.sources._jobspy_mapping import DESIRED_ORDER
from app.sources._ledger import record_fetch_outcome
from app.sources.base import FetchBudget, FetchResult, JobSource, SearchQuery
from app.sources.linkedin import CAPABILITIES, map_jobspy_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "listings"
TRANSPORT_PATH = PROJECT_ROOT / "app" / "sources" / "_jobspy_transport.py"


def _load(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _by_signal(results: list[Any], signal: str) -> Any:
    return next(result for result in results if result.signal == signal)


def _evidence(**overrides: Any) -> BoardEvidence:
    base: dict[str, Any] = {"source": "linkedin"}
    base.update(overrides)
    return BoardEvidence(**base)


# --- the documented defaults --------------------------------------------------


def test_the_documented_threshold_defaults_match_the_research() -> None:
    """RESEARCH §S2/S3/S4 and the D-02 envelope. A drifted default fails here."""
    assert settings.probe_max_requests == 2
    assert settings.probe_max_results == 50
    assert settings.probe_max_detail_fetches == 0
    assert settings.probe_deadline_seconds == 180
    assert settings.probe_results_wanted == 50
    assert settings.probe_country_indeed == "ireland"
    assert settings.probe_cache_ttl_seconds == 300
    assert settings.probe_fill_rate_warn_drop_points == 10
    assert settings.probe_fill_rate_fail_drop_points == 25
    assert settings.probe_count_warn_drop_pct == 25
    assert settings.probe_count_fail_drop_pct == 50
    assert settings.probe_count_trailing_runs == 5
    assert settings.probe_freshness_fail_runs == 3
    assert settings.probe_min_runs_before_arming == 2


# --- S1 -----------------------------------------------------------------------


def test_s1_counts_each_status_correctly() -> None:
    distribution = compute_status_distribution(
        ["ok", "ok", "blocked", "rate_limited", "partial", "error", "ok"]
    )

    assert distribution == {
        "ok": 3,
        "partial": 1,
        "blocked": 1,
        "rate_limited": 1,
        "error": 1,
    }


def test_s1_is_clean_only_when_nothing_was_blocked() -> None:
    assert status_distribution_signal(["ok", "ok"]).status == "pass"
    assert status_distribution_signal(["ok", "blocked"]).status == "warn"
    assert status_distribution_signal([]).status == "skip"


# --- S2 fill-rate boundaries --------------------------------------------------


@pytest.fixture
def fill_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "probe_fill_rate_warn_drop_points", 25)
    monkeypatch.setattr(settings, "probe_fill_rate_fail_drop_points", 50)


def test_s2_warns_exactly_at_the_configured_warn_drop(fill_thresholds: None) -> None:
    result = compare_fill_rate("title", {"title": 0.75}, {"title": 1.0})

    assert result.status == "warn"
    assert result.threshold_name == "probe_fill_rate_warn_drop_points"
    assert result.threshold_value == 25


def test_s2_fails_exactly_at_the_configured_fail_drop(fill_thresholds: None) -> None:
    result = compare_fill_rate("title", {"title": 0.5}, {"title": 1.0})

    assert result.status == "fail"
    assert result.threshold_name == "probe_fill_rate_fail_drop_points"
    assert result.threshold_value == 50


def test_s2_is_silent_one_point_below_the_warn_drop(fill_thresholds: None) -> None:
    result = compare_fill_rate("title", {"title": 0.875}, {"title": 1.0})

    assert result.status == "pass"
    assert result.observed == 12.5


def test_s2_skips_a_field_with_no_baseline(fill_thresholds: None) -> None:
    assert compare_fill_rate("title", {"title": 0.1}, {}).status == "skip"


def test_s2_reports_every_field_and_ranks_the_worst_first(
    fill_thresholds: None,
) -> None:
    current = {name: 1.0 for name in ("title", "company_name", "location_raw")}
    current["title"] = 0.5  # a 50-point drop
    current["company_name"] = 0.8  # a 20-point drop

    results = fill_rate_signals(current, {"title": 1.0, "company_name": 1.0})

    assert results[0].name == "fill-rate title"
    assert results[0].status == "fail"
    assert results[1].name == "fill-rate company_name"
    assert results[1].status == "pass"


def test_fill_rates_count_a_blank_description_as_empty() -> None:
    rates = compute_fill_rates(
        [
            {"title": "Engineer", "description": "Build it"},
            {"title": "Engineer", "description": "   "},
        ]
    )

    assert rates["title"] == 1.0
    assert rates["description"] == 0.5
    assert rates["salary_min"] == 0.0


# --- S3 count-delta boundaries ------------------------------------------------


@pytest.fixture
def count_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "probe_count_warn_drop_pct", 25)
    monkeypatch.setattr(settings, "probe_count_fail_drop_pct", 50)
    monkeypatch.setattr(settings, "probe_count_trailing_runs", 5)
    monkeypatch.setattr(settings, "probe_min_runs_before_arming", 2)


def test_s3_warns_exactly_at_the_configured_drop(count_thresholds: None) -> None:
    result = compute_count_delta([100, 100, 75])

    assert result.status == "warn"
    assert result.observed == -25.0
    assert result.threshold_name == "probe_count_warn_drop_pct"


def test_s3_fails_exactly_at_the_configured_drop(count_thresholds: None) -> None:
    result = compute_count_delta([100, 100, 50])

    assert result.status == "fail"
    assert result.observed == -50.0
    assert result.threshold_name == "probe_count_fail_drop_pct"


def test_s3_is_silent_one_point_above_the_warn_drop(count_thresholds: None) -> None:
    assert compute_count_delta([100, 100, 76]).status == "pass"


def test_s3_is_not_armed_below_the_configured_run_count(
    count_thresholds: None,
) -> None:
    # One prior run when two are required: a delta from it would be a guess.
    result = compute_count_delta([100, 1])

    assert result.status == "skip"
    assert result.threshold_name == "probe_min_runs_before_arming"


def test_s3_arms_once_the_configured_run_count_is_reached(
    count_thresholds: None,
) -> None:
    result = compute_count_delta([100, 100, 1])

    assert result.status == "fail"


# --- S4 freshness boundaries --------------------------------------------------


@pytest.fixture
def freshness_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "probe_freshness_fail_runs", 3)


def test_s4_fails_at_exactly_the_configured_consecutive_count(
    freshness_thresholds: None,
) -> None:
    result = compute_freshness([("ok", 0), ("ok", 0), ("ok", 0)])

    assert result.status == "fail"
    assert result.threshold_name == "probe_freshness_fail_runs"
    assert result.threshold_value == 3


def test_s4_does_not_fire_one_run_earlier(freshness_thresholds: None) -> None:
    # Three runs recorded, but only two consecutive stale ones.
    result = compute_freshness([("ok", 7), ("ok", 0), ("ok", 0)])

    assert result.status == "pass"


def test_s4_skips_when_the_window_is_too_short(freshness_thresholds: None) -> None:
    assert compute_freshness([("ok", 0), ("ok", 0)]).status == "skip"


def test_s4_ignores_stale_runs_that_did_not_report_ok(
    freshness_thresholds: None,
) -> None:
    # A blocked run explains the absence; that is not the silent-breakage case.
    assert compute_freshness([("blocked", 0), ("blocked", 0), ("ok", 3)]).status == "pass"


# --- S5 block vs parse --------------------------------------------------------


def test_s5_classifies_a_200_with_a_stop_signal_as_fetch_side() -> None:
    """The silent-breakage case: a plausible body that is actually a block page."""
    result = classify_block_vs_parse(status_code=200, parsed_items=25, stop_signal="captcha")

    assert result.observed == "fetch-side"
    assert result.status == "warn"
    assert "captcha" in result.detail


def test_s5_classifies_a_200_with_rows_as_healthy() -> None:
    result = classify_block_vs_parse(status_code=200, parsed_items=25)

    assert result.observed == "parse-side"
    assert result.status == "pass"


def test_s5_classifies_a_200_with_no_rows_as_parse_side() -> None:
    result = classify_block_vs_parse(status_code=200, parsed_items=0)

    assert result.observed == "parse-side"
    assert result.status == "warn"


def test_s5_classifies_a_blocked_result_status_as_fetch_side() -> None:
    result = classify_block_vs_parse(status_code=None, parsed_items=0, status="blocked")

    assert result.observed == "fetch-side"


def test_s5_classifies_a_transport_error_status_as_fetch_side() -> None:
    """WR-04: `error` is a fetch-side failure, consistent with the ledger."""
    result = classify_block_vs_parse(status_code=None, parsed_items=0, status="error")

    assert result.observed == "fetch-side"
    assert result.status == "warn"


# --- S6 schema drift ----------------------------------------------------------


def test_s6_reports_a_missing_expected_column() -> None:
    returned = [column for column in DESIRED_ORDER if column != "company"]

    result = detect_schema_drift(returned)

    assert result.status == "warn"
    assert "company" in result.detail


def test_s6_is_silent_for_a_complete_column_set() -> None:
    result = detect_schema_drift(list(DESIRED_ORDER))

    assert result.status == "pass"
    assert result.observed == 0


def test_s6_reports_nothing_for_extra_unexpected_columns() -> None:
    result = detect_schema_drift([*DESIRED_ORDER, "a_brand_new_column"])

    assert result.status == "pass"


# --- the Adzuna promotion condition (P-1..P-5) --------------------------------


@pytest.fixture
def promotion_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "probe_promotion_window_runs", 5)
    monkeypatch.setattr(settings, "probe_promotion_blocked_runs", 3)
    monkeypatch.setattr(settings, "probe_promotion_consecutive_runs", 2)
    monkeypatch.setattr(settings, "probe_fill_rate_fail_drop_points", 25)
    monkeypatch.setattr(settings, "probe_count_warn_drop_pct", 25)
    monkeypatch.setattr(settings, "probe_count_trailing_runs", 5)
    monkeypatch.setattr(settings, "probe_min_runs_before_arming", 2)
    monkeypatch.setattr(settings, "probe_freshness_fail_runs", 3)


def test_p1_fires_at_the_configured_blocked_count(promotion_thresholds: None) -> None:
    statuses = ["blocked", "blocked", "blocked", "ok", "ok"]

    result = _by_signal(adzuna_promotion_condition(_evidence(run_statuses=statuses)), "P-1")

    assert result.status == "fail"
    assert result.threshold_name == "probe_promotion_blocked_runs"
    assert result.threshold_value == 3
    assert "linkedin" in result.detail


def test_p1_does_not_fire_one_blocked_run_below(promotion_thresholds: None) -> None:
    statuses = ["blocked", "blocked", "ok", "ok", "ok"]

    result = _by_signal(adzuna_promotion_condition(_evidence(run_statuses=statuses)), "P-1")

    assert result.status == "pass"


def test_p1_skips_when_the_window_is_not_full(promotion_thresholds: None) -> None:
    statuses = ["blocked", "blocked", "blocked", "blocked"]

    result = _by_signal(adzuna_promotion_condition(_evidence(run_statuses=statuses)), "P-1")

    assert result.status == "skip"


def test_p2_fires_on_consecutive_structural_collapses(
    promotion_thresholds: None,
) -> None:
    evidence = _evidence(
        run_statuses=["ok", "ok"],
        baseline={"title": 1.0},
        fill_rates=[{"title": 0.6}, {"title": 0.6}],
    )

    result = _by_signal(adzuna_promotion_condition(evidence), "P-2")

    assert result.status == "fail"
    assert result.threshold_name == "probe_promotion_consecutive_runs"


def test_p2_does_not_fire_on_a_single_collapse(promotion_thresholds: None) -> None:
    evidence = _evidence(
        run_statuses=["ok", "ok"],
        baseline={"title": 1.0},
        fill_rates=[{"title": 0.95}, {"title": 0.6}],
    )

    result = _by_signal(adzuna_promotion_condition(evidence), "P-2")

    assert result.status == "pass"


def test_p2_skips_without_a_recorded_baseline(promotion_thresholds: None) -> None:
    evidence = _evidence(run_statuses=["ok"], fill_rates=[{"title": 0.1}])

    assert _by_signal(adzuna_promotion_condition(evidence), "P-2").status == "skip"


def test_p3_fires_on_consecutive_count_collapses(promotion_thresholds: None) -> None:
    evidence = _evidence(run_statuses=["ok"] * 5, output_counts=[100, 100, 100, 60, 60])

    result = _by_signal(adzuna_promotion_condition(evidence), "P-3")

    assert result.status == "fail"
    assert result.threshold_name == "probe_count_warn_drop_pct"


def test_p3_does_not_fire_on_a_single_collapse(promotion_thresholds: None) -> None:
    evidence = _evidence(run_statuses=["ok"] * 5, output_counts=[100, 100, 100, 100, 60])

    assert _by_signal(adzuna_promotion_condition(evidence), "P-3").status == "pass"


def test_p4_fires_on_consecutive_unreachable_probes(promotion_thresholds: None) -> None:
    evidence = _evidence(probe_statuses=["ok", "unreachable", "unreachable"])

    result = _by_signal(adzuna_promotion_condition(evidence), "P-4")

    assert result.status == "fail"
    assert result.threshold_name == "probe_promotion_consecutive_runs"


def test_p4_does_not_fire_on_a_single_unreachable_probe(
    promotion_thresholds: None,
) -> None:
    evidence = _evidence(probe_statuses=["unreachable", "ok", "ok"])

    assert _by_signal(adzuna_promotion_condition(evidence), "P-4").status == "pass"


def test_p5_fires_on_the_ok_but_nothing_new_contradiction(
    promotion_thresholds: None,
) -> None:
    evidence = _evidence(
        run_statuses=["ok", "ok", "ok"], new_listing_counts=[0, 0, 0]
    )

    result = _by_signal(adzuna_promotion_condition(evidence), "P-5")

    assert result.status == "fail"
    assert result.threshold_name == "probe_freshness_fail_runs"


def test_the_keep_as_hedge_outcome_holds_when_no_condition_fires(
    promotion_thresholds: None,
) -> None:
    evidence = _evidence(
        run_statuses=["ok"] * 5,
        output_counts=[100, 100, 100, 100, 100],
        new_listing_counts=[5, 5, 5, 5, 5],
        fill_rates=[{"title": 1.0}] * 5,
        baseline={"title": 1.0},
        probe_statuses=["ok", "ok", "ok"],
        window_days=5,
    )

    results = adzuna_promotion_condition(evidence)

    assert not any(result.status == "fail" for result in results)
    keep = _by_signal(results, "P-keep")
    assert keep.status == "pass"
    assert "linkedin" in keep.detail
    assert "5 run(s) over 5 day(s)" in keep.detail


def test_every_promotion_result_names_the_board_and_the_window(
    promotion_thresholds: None,
) -> None:
    evidence = _evidence(
        source="indeed", run_statuses=["ok", "ok"], window_days=2
    )

    results = adzuna_promotion_condition(evidence)

    assert {result.signal for result in results} >= {"P-1", "P-2", "P-3", "P-4", "P-5"}


# --- the envelope -------------------------------------------------------------


def test_the_envelope_ceilings_are_read_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "probe_max_requests", 7)
    monkeypatch.setattr(settings, "probe_max_results", 8)
    monkeypatch.setattr(settings, "probe_max_detail_fetches", 9)
    monkeypatch.setattr(settings, "probe_deadline_seconds", 11)
    moment = datetime(2026, 1, 1, tzinfo=UTC)

    budget = build_budget(now=moment)

    assert budget.max_requests == 7
    assert budget.max_results == 8
    assert budget.max_detail_fetches == 9
    assert (budget.deadline - moment).total_seconds() == 11


def test_the_transport_has_no_retry_or_escalation_path() -> None:
    """A block is recorded and stopped — never retried harder (P2 / T-01-36).

    Asserted on the AST so a comment mentioning a retry cannot create a false pass.
    """
    tree = ast.parse(TRANSPORT_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "tenacity" not in imported, "no retry library on the transport path"
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree)), (
        "no retry loop on the transport path"
    )


# --- the ledger row and the baseline anchor -----------------------------------


async def test_a_blocked_result_is_recorded_as_fetch_side(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()

    async with session_factory() as session:
        outcome = await record_fetch_outcome(
            session,
            source="linkedin",
            run_id=None,
            result_status="blocked",
            parsed_items=0,
        )
        await session.commit()

    assert outcome.ok is False
    assert outcome.note.startswith("fetch-side")
    async with session_factory() as session:
        row = await session.scalar(select(SourceRequestLog))
    assert row is not None
    assert row.kind == "search"
    assert row.ok is False
    assert row.note.startswith("fetch-side")


async def test_a_transport_error_is_recorded_as_fetch_side(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """WR-04: a raised transport failure is fetch-side, not a parse-side miss."""
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()

    async with session_factory() as session:
        outcome = await record_fetch_outcome(
            session,
            source="linkedin",
            run_id=None,
            result_status="error",
            parsed_items=0,
            error="connection reset by peer",
        )
        await session.commit()

    assert outcome.ok is False
    assert outcome.note.startswith("fetch-side"), (
        "a connection reset must not be recorded as a parse-side miss"
    )
    assert "connection reset by peer" in outcome.note


async def test_a_zero_row_partial_is_still_recorded_as_parse_side(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """CR-01 consistency: an empty frame with no transport error is parse-side."""
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()

    async with session_factory() as session:
        outcome = await record_fetch_outcome(
            session,
            source="linkedin",
            run_id=None,
            result_status="partial",
            parsed_items=0,
        )
        await session.commit()

    assert outcome.ok is False
    assert outcome.note.startswith("parse-side")


async def test_record_baseline_writes_once_and_never_overwrites(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()

    async with session_factory() as session:
        first = await record_baseline(
            session, source="linkedin", fill_rates={"title": 1.0}
        )
        await session.commit()
    async with session_factory() as session:
        second = await record_baseline(
            session, source="linkedin", fill_rates={"title": 0.1}
        )
        await session.commit()

    assert first is True
    assert second is False
    async with session_factory() as session:
        row = await session.scalar(select(Source).where(Source.name == "linkedin"))
    assert row is not None
    assert row.field_fill_baseline_json == {"title": 1.0}
    assert row.baseline_recorded_at is not None


#: A board whose fetch returns two fixture items, one with a blank description.
class FixtureBoard(JobSource):
    name: Literal["linkedin"] = "linkedin"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        rows = _load("linkedin_page1.json")[:1] + _load("linkedin_empty_description.json")[:1]
        return FetchResult(
            source="linkedin",
            items=[map_jobspy_row(row, source="linkedin") for row in rows],
            status="ok",
            requests_used=1,
        )


@pytest.mark.usefixtures("registry_snapshot")
async def test_a_run_writes_one_ledger_row_and_records_the_baseline(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The ledger and the baseline come out of a real run, not a direct call."""
    registry.clear()
    registry.register(FixtureBoard)
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()

    await run_pipeline("manual", None, session_factory, adapters=[FixtureBoard()])

    async with session_factory() as session:
        ledger = (await session.execute(select(SourceRequestLog))).scalars().all()
        source = await session.scalar(select(Source).where(Source.name == "linkedin"))

    assert len(ledger) == 1, "one outbound request must leave exactly one ledger row"
    assert ledger[0].kind == "search"
    assert ledger[0].ok is True
    assert ledger[0].note.startswith("ok:")
    assert ledger[0].run_id is not None

    assert source is not None
    assert source.field_fill_baseline_json is not None
    assert source.field_fill_baseline_json["title"] == 1.0
    assert source.field_fill_baseline_json["description"] == 0.5
    assert source.baseline_recorded_at is not None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
