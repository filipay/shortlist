"""Five real caller paths use global selection, not their explicit environment keyword."""

import json

from sqlalchemy import select

from app import llm
from app.config import settings
from app.cv.llm_extract import ExtractionError, extract_facts
from app.db import session as session_module
from app.db.models import Listing, LlmCall
from app.domain.cv import TailoringPatch
from app.pipeline.draft import draft_screening_answers
from app.pipeline.rank import rank_listing
from app.pipeline.tailor import tailor_listing
from tests.llm.test_model_selection import model_wire as model_wire
from tests.llm.test_model_selection import save_pair
from tests.pipeline.test_rank_stage import NOW, _add_listing, _facts, _seed_run


async def test_all_five_callers_request_saved_pair_with_fresh_production_backends(
    client, session_factory, monkeypatch, model_wire
):
    requests, state = model_wire
    await save_pair(session_factory)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(settings, "opencode_model", "environment-not-advertised")
    run_id = await _seed_run(session_factory)
    listing_id = await _add_listing(session_factory, title="Selection Role")
    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        state["payload"] = {"skills": 0.8, "seniority": 0.8, "domain": 0.8,
            "location": 0.8, "evidence": 0.8, "rationale": "Grounded"}
        ranked = await rank_listing(llm.get_llm_backend(), session, listing=listing, facts=_facts(),
            run_id=run_id, criteria_version=0, now=NOW)
        assert ranked is not None and ranked.model == "X"
        await session.commit()
        state["payload"] = {"listing_id": listing_id}
        outcome = await tailor_listing(llm.get_llm_backend(), session, listing=listing,
            facts=_facts(), requirements=[], now=NOW)
        assert isinstance(outcome.patch, TailoringPatch) and outcome.requested_model == "X"
        await session.commit()
        state["payload"] = {"answers": [
            {"question": "Why?", "answer": "Relevant experience.", "evidence_ids": []}
        ]}
        drafted = await draft_screening_answers(llm.get_llm_backend(), session, listing=listing,
            facts=_facts(), questions=["Why?"], now=NOW)
        assert drafted is not None
        await session.commit()
    # Extraction deliberately has no request database session. Empty extraction is a
    # downstream domain refusal, not a transport stub that swallows model selection.
    state["payload"] = {"cv_json": "{}"}
    try:
        await extract_facts(llm.get_llm_backend(), tex_source=r"\documentclass{article}")
    except ExtractionError:
        pass
    client._transport.app.dependency_overrides[llm.get_llm_backend] = llm.get_llm_backend
    state["payload"] = {"acknowledged": True}
    assert (await client.post("/settings/llm-test")).status_code == 200
    sessions = [json.loads(r.content) for r in requests if r.url.path == "/api/session"]
    assert len(sessions) == 5
    assert [body["model"] for body in sessions] == [{"id": "X", "providerID": "B"}] * 5
    assert all(set(body) == {"model"} for body in sessions)  # no new tool grants
    async with session_factory() as session:
        calls = list((await session.scalars(select(LlmCall))).all())
    assert len(calls) == 4
    assert all(row.provider is None and row.model == "X" for row in calls)


async def test_background_rank_constructs_fresh_backend_and_reads_global_selection(
    session_factory, monkeypatch, model_wire, tmp_path
):
    from app.pipeline import rank
    from tests.pipeline.test_rank_stage import FIXTURE

    requests, state = model_wire
    await save_pair(session_factory)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(settings, "opencode_model", "environment-not-advertised")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))
    (tmp_path / "cv.yaml").write_text(FIXTURE.read_text())
    monkeypatch.setattr(rank, "_RANKING_TASK", None)
    state["payload"] = {"skills": 0.8, "seniority": 0.8, "domain": 0.8,
        "location": 0.8, "evidence": 0.8, "rationale": "Grounded"}
    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Background selection role")
    assert rank.start_ranking_task(run_id, session_factory) is None
    await rank._RANKING_TASK
    sessions = [json.loads(r.content) for r in requests if r.url.path == "/api/session"]
    assert len(sessions) == 1
    assert sessions[0]["model"] == {"id": "X", "providerID": "B"}
