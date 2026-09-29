"""RANK-01 / RANK-05 / RANK-06 / RANK-07 — the ranking stage end to end.

A stubbed backend implements `complete_structured` and records what it received, so
the call SHAPE is asserted directly: exactly one call per listing, exactly one
listing per prompt (D-86), a failure isolated to its listing (D-95), and a
fabricated CV fact id dropped before the write (RANK-05).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cv.factstore import load_facts
from app.db.models import Listing, LlmCall, Run, Score, Search, Source
from app.domain.cv import CvFacts, iter_fact_ids
from app.domain.schemas.ranking import RankingResponse, RequirementFit
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult
from app.pipeline.rank import (
    RANK_SYSTEM_PROMPT,
    build_ranking_parts,
    rank_listing,
    run_ranking,
)

NOW = datetime(2026, 9, 22, tzinfo=UTC)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cv" / "awesomecv_standin.yaml"

GENUINE_FACT_ID = "bul/northwind-labs-2021/1"
FABRICATED_FACT_ID = "bul/does-not-exist/0"


class StubBackend:
    """A fixed structured response that records the calls it received."""

    def __init__(
        self,
        response: RankingResponse | None = None,
        *,
        fail_marker: str | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response or RankingResponse(
            skills=0.8,
            seniority=0.6,
            domain=0.5,
            location=1.0,
            evidence=0.4,
            rationale="Grounded in the listing's stated requirements and the CV facts.",
            requirements=[RequirementFit(text="Python", verdict="met", evidence_id="skill.python")],
        )
        self._fail_marker = fail_marker

    async def health(self) -> ProbeOutcome:
        return ProbeOutcome(reachable=True)

    async def discover_models(self) -> DiscoveryResult:
        return DiscoveryResult(reachable=True)

    async def complete_structured(
        self,
        *,
        schema: type,
        system: str,
        parts: Sequence[str],
        model: str | None = None,
        agent: str | None = None,
        tools: Sequence[str] = (),
        retries: int | None = None,
    ) -> StructuredCallResult:
        text = "\n".join(parts)
        self.calls.append({"system": system, "text": text, "tools": tuple(tools)})
        if self._fail_marker is not None and self._fail_marker in text:
            return StructuredCallResult(ok=False, status="invalid", error="schema invalid")
        return StructuredCallResult(
            ok=True,
            status="ok",
            data=self._response,
            provider="opencode",
            model="minimax-m3",
        )


async def _seed_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    started_at: datetime = NOW,
    register_source: bool = True,
) -> int:
    async with session_factory() as session:
        if register_source:
            session.add(Source(name="linkedin", display_name="Linkedin"))
        run = Run(trigger="manual", status="running", started_at=started_at)
        session.add(run)
        await session.commit()
        return int(run.id)


async def _add_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    title: str,
    description: str | None = "Build the thing.",
    salary_min: float | None = None,
    salary_max: float | None = None,
) -> int:
    async with session_factory() as session:
        listing = Listing(
            canonical_url=f"https://example.com/jobs/{title.replace(' ', '-').lower()}",
            title=title,
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            first_seen_at=NOW,
            last_seen_at=NOW,
            content_hash=f"hash-{title}",
            created_at=NOW,
            updated_at=NOW,
            is_active=True,
        )
        session.add(listing)
        await session.commit()
        return int(listing.id)


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(table)) or 0)


def _facts() -> CvFacts:
    return load_facts(FIXTURE)


# --- the call shape (D-86) -----------------------------------------------------


def test_the_system_prompt_is_a_frozen_constant_with_no_interpolation() -> None:
    """§6.3 / m5 / T-05-01: untrusted content has no path into `system`."""
    source = (Path(__file__).resolve().parents[2] / "app" / "pipeline" / "rank.py").read_text(
        encoding="utf-8"
    )

    assert "RANK_SYSTEM_PROMPT = (" in source, "must be a module-level plain literal"
    assert "RANK_SYSTEM_PROMPT = f" not in source
    assert "{" not in RANK_SYSTEM_PROMPT
    assert "%s" not in RANK_SYSTEM_PROMPT


async def test_prompt_contains_exactly_one_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Alpha Engineer")
    await _add_listing(session_factory, title="Beta Engineer")

    stub = StubBackend()
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert len(stub.calls) == 2, "one call per listing"
    alpha = [call for call in stub.calls if "Alpha Engineer" in call["text"]]
    assert len(alpha) == 1
    assert "Beta Engineer" not in alpha[0]["text"], "no sibling listing in a prompt"
    assert alpha[0]["system"] == RANK_SYSTEM_PROMPT
    assert alpha[0]["tools"] == (), "tools is explicitly empty on every ranking call"


async def test_a_successful_listing_produces_one_score_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    listing_id = await _add_listing(session_factory, title="Scored Role")

    await run_ranking(session_factory, run_id=run_id, llm=StubBackend(), facts=_facts())

    async with session_factory() as session:
        rows = (await session.execute(select(Score))).scalars().all()

    assert len(rows) == 1
    assert rows[0].listing_id == listing_id
    assert rows[0].factor_scores_json == {
        "skills": 0.8,
        "seniority": 0.6,
        "domain": 0.5,
        "location": 1.0,
        "evidence": 0.4,
    }
    assert "compensation" not in rows[0].factor_scores_json
    assert rows[0].criteria_version == 0
    assert rows[0].provider == "opencode"
    assert rows[0].model == "minimax-m3"


async def test_failed_listing_is_isolated(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    broken_id = await _add_listing(session_factory, title="Broken Role")
    good_id = await _add_listing(session_factory, title="Good Role")

    stub = StubBackend(fail_marker="Broken Role")
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    async with session_factory() as session:
        calls = (await session.execute(select(LlmCall))).scalars().all()
        scores = (await session.execute(select(Score))).scalars().all()

    assert len(calls) == 2, "both calls are audited"
    assert all(call.purpose == "rank" for call in calls)
    assert len(scores) == 1, "the failed listing gets no score row"
    assert scores[0].listing_id == good_id
    assert scores[0].listing_id != broken_id


async def test_absolute_score_is_stable_across_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_run = await _seed_run(session_factory)
    second_run = await _seed_run(session_factory, register_source=False)
    await _add_listing(session_factory, title="Stable Role")

    await run_ranking(session_factory, run_id=first_run, llm=StubBackend(), facts=_facts())
    await run_ranking(session_factory, run_id=second_run, llm=StubBackend(), facts=_facts())

    async with session_factory() as session:
        rows = (await session.execute(select(Score).order_by(Score.run_id))).scalars().all()

    assert len(rows) == 2
    assert rows[0].factor_scores_json == rows[1].factor_scores_json


async def test_listing_with_no_description_or_salary_still_scores(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Sparse Role", description=None)

    stub = StubBackend()
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    async with session_factory() as session:
        row = (await session.execute(select(Score))).scalar_one()

    assert "compensation" not in row.factor_scores_json
    assert "compensation:" not in stub.calls[0]["text"], (
        "an absent salary means the compensation factor is not sent at all"
    )


async def test_zero_survivor_pass_writes_zero_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    stub = StubBackend()

    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert stub.calls == []
    assert await _count(session_factory, Score) == 0
    assert await _count(session_factory, LlmCall) == 0


# --- the work-mode ranking hint -------------------------------------------------


def test_hybrid_work_mode_adds_a_ranking_hint_and_other_modes_do_not() -> None:
    facts = _facts()
    listing = SimpleNamespace(
        title="Hybrid Role",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        salary_min=None,
        salary_max=None,
    )
    weights = {
        "skills": 1.0,
        "seniority": 1.0,
        "domain": 1.0,
        "location": 1.0,
        "evidence": 1.0,
        "compensation": 1.0,
    }

    hybrid = "\n".join(
        build_ranking_parts(facts, listing, weights, work_mode="hybrid")
    ).casefold()
    assert "work-mode preference" in hybrid
    assert "hybrid" in hybrid

    for mode in ("any", "remote", "onsite"):
        text = "\n".join(
            build_ranking_parts(facts, listing, weights, work_mode=mode)
        ).casefold()
        assert "work-mode preference" not in text, f"{mode} must not add a hint"


async def test_run_ranking_threads_the_stored_work_mode_into_the_prompt(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(
            Search(
                name="Hybrid roles",
                enabled=True,
                criteria_json={"keywords": "python", "work_mode": "hybrid"},
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Some Role")
    stub = StubBackend()

    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert len(stub.calls) == 1
    assert "work-mode preference" in stub.calls[0]["text"].casefold()


# --- the required-experience ranking hint ---------------------------------------


def test_a_stated_years_floor_adds_a_user_turn_ranking_hint() -> None:
    facts = _facts()
    listing = SimpleNamespace(
        title="Senior Role",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="5+ years required.",
        salary_min=None,
        salary_max=None,
    )
    weights = {
        "skills": 1.0,
        "seniority": 1.0,
        "domain": 1.0,
        "location": 1.0,
        "evidence": 1.0,
        "compensation": 1.0,
    }

    text = "\n".join(build_ranking_parts(facts, listing, weights))

    assert "5+ years" in text, "the matched fragment is quoted from the listing"
    assert "floor of 5 years" in text, "the stated floor is named"
    assert "not a hard filter" in text
    assert "LISTING (untrusted job-board text" in text, "the listing block still builds"


async def test_the_years_hint_never_reaches_the_system_turn(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Years Role", description="5+ years required.")

    stub = StubBackend()
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert len(stub.calls) == 1
    assert "STATED EXPERIENCE REQUIREMENT" in stub.calls[0]["text"]
    assert stub.calls[0]["system"] == RANK_SYSTEM_PROMPT, (
        "the hint travels in the user turn only, never in `system`"
    )


def test_a_non_requirement_adds_no_years_hint() -> None:
    facts = _facts()
    weights = {
        "skills": 1.0,
        "seniority": 1.0,
        "domain": 1.0,
        "location": 1.0,
        "evidence": 1.0,
        "compensation": 1.0,
    }

    for description in ("5+ years of experience preferred", "Build the thing.", None):
        listing = SimpleNamespace(
            title="Some Role",
            company_name="Acme",
            location_raw="Dublin, Ireland",
            description=description,
            salary_min=None,
            salary_max=None,
        )

        text = "\n".join(build_ranking_parts(facts, listing, weights))

        assert "STATED EXPERIENCE REQUIREMENT" not in text, (
            f"{description!r} must add no years hint"
        )


# --- the never-fabricate grounding (RANK-05) -----------------------------------


async def test_rationale_ids_are_cv_fact_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    facts = _facts()
    assert GENUINE_FACT_ID in set(iter_fact_ids(facts))
    assert FABRICATED_FACT_ID not in set(iter_fact_ids(facts))

    run_id = await _seed_run(session_factory)
    listing_id = await _add_listing(session_factory, title="Grounding Role")
    response = RankingResponse(
        skills=0.5,
        rationale="One requirement is met, one is only partly evidenced.",
        requirements=[
            RequirementFit(text="Python experience", verdict="met", evidence_id=GENUINE_FACT_ID),
            RequirementFit(text="Kubernetes", verdict="partial", evidence_id=FABRICATED_FACT_ID),
        ],
    )
    stub = StubBackend(response)

    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        assert listing is not None
        record = await rank_listing(
            stub,
            session,
            listing=listing,
            facts=facts,
            run_id=run_id,
            criteria_version=0,
            now=NOW,
        )
        await session.commit()

    assert record is not None, "an unknown evidence id degrades one requirement, not the listing"
    stored = json.dumps(list(record.requirements))

    assert GENUINE_FACT_ID in stored
    assert FABRICATED_FACT_ID not in stored, "a fabricated id is never persisted"

    kubernetes = [entry for entry in record.requirements if entry["text"] == "Kubernetes"]
    assert len(kubernetes) == 1, "the entry survives with its text and verdict"
    assert kubernetes[0]["verdict"] == "partial"
    assert kubernetes[0]["evidence_id"] is None

    async with session_factory() as session:
        scores = (await session.execute(select(Score))).scalars().all()
    assert len(scores) == 1, "the listing still scores"
