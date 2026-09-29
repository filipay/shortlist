"""260929-pan — the bounded render→compile→drop loop in ``compile_tailored``.

Hermetic in the shape of ``tests/verify/test_block_no_repair.py``: a temporary
``artifacts_dir`` and an injected engine whose compile returns a SCRIPTED sequence
of page counts, with ``extract_pdf_text`` monkeypatched to a committed extraction.
No LaTeX engine, no socket.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing
from app.db.repositories.cv_artifact_repo import CvArtifactRecord
from app.domain.cv import DropBullet, TailoringPatch
from app.latex.base import CompileResult, EngineProbe
from app.pipeline import tailor as tailor_module
from app.pipeline.tailor import MAX_PAGE_TRIM_PASSES, compile_tailored
from tests.pipeline.test_rank_stage import _add_listing
from tests.verify.fixtures import VERIFY_FIXTURES, load_standin_facts

NOW = datetime(2026, 9, 24, tzinfo=UTC)
BULLET2 = "bul/northwind-labs-2021/2"
BULLET3 = "bul/northwind-labs-2021/3"

LAYER_ONE_CHECKS = {
    "id_containment",
    "entity_resolvable",
    "bullet_conservation",
    "temporal_consistency",
    "requirement_evidence",
}


class ScriptedEngine:
    """A compile whose page count follows a script; ``None`` means a failed compile."""

    def __init__(self, outcomes: list[int | None]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[str] = []

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        self.calls.append(tex)
        workdir.mkdir(parents=True, exist_ok=True)
        outcome = self.outcomes.pop(0) if self.outcomes else 1
        if outcome is None:
            return CompileResult(ok=False, engine="fake", error="boom", error_kind="compile_error")
        pdf = workdir / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake\n")
        return CompileResult(
            ok=True,
            engine="fake",
            pdf_path=str(pdf),
            page_count=outcome,
            tex_hash="a" * 64,
            pdf_hash="b" * 64,
            compile_log="ok",
        )

    async def health(self) -> EngineProbe:
        return EngineProbe(available=True)


async def _compile(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
    *,
    title: str,
    patch: TailoringPatch,
    outcomes: list[int | None],
    extract: str = "base_extract.txt",
) -> tuple[int, CvArtifactRecord, ScriptedEngine]:
    listing_id = await _add_listing(session_factory, title=title)
    text = (VERIFY_FIXTURES / extract).read_text(encoding="utf-8")
    monkeypatch.setattr(tailor_module, "extract_pdf_text", lambda path: text)
    engine = ScriptedEngine(outcomes)
    async with session_factory() as session:
        listing = await session.get(Listing, listing_id)
        record = await compile_tailored(
            session,
            listing=listing,
            facts=load_standin_facts(),
            patch=patch,
            base_cv_version_id=None,
            engine=engine,
            artifacts_dir=tmp_path / "artifacts",
            now=NOW,
        )
        await session.commit()
    return listing_id, record, engine


def _check_status(record, check_id: str) -> str:
    checks = (record.verification_json or {}).get("checks") or []
    return next(check["status"] for check in checks if check["id"] == check_id)


# --- the tracer: one over-budget CV drops its lowest-value bullet and fits ------


async def test_a_trim_drops_the_lowest_value_bullet_and_recompiles_to_fit(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Trim Fits",
        patch=TailoringPatch(listing_id=1),
        outcomes=[3, 2],
    )

    assert record.compile_status == "ok"
    assert record.page_count == 2
    assert len(engine.calls) == 2, "one initial compile plus one trim recompile"

    ops = record.patch_json["ops"]
    assert [op["op"] for op in ops] == ["drop_bullet"]
    assert ops[0]["bullet_id"] == BULLET3
    assert ops[0]["reason"], "a trim carries a non-empty reason"

    assert len(record.change_log_json) == 1
    change = record.change_log_json[0]
    assert change["op"] == "drop_bullet"
    assert change["target_id"] == BULLET3
    assert change["detail"] == ops[0]["reason"]


async def test_the_final_trimmed_plan_passes_all_layer_one_checks(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, record, _ = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Trim Layer One",
        patch=TailoringPatch(listing_id=1),
        outcomes=[3, 2],
    )

    checks = (record.verification_json or {}).get("checks") or []
    assert {check["id"] for check in checks} >= LAYER_ONE_CHECKS
    assert all(check["status"] == "pass" for check in checks if check["id"] in LAYER_ONE_CHECKS)
    assert _check_status(record, "bullet_conservation") == "pass"


# --- the no-trim identity -------------------------------------------------------


async def test_an_in_budget_cv_compiles_once_and_keeps_the_input_patch(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch = TailoringPatch(listing_id=1)
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="In Budget",
        patch=patch,
        outcomes=[2],
    )

    assert record.compile_status == "ok"
    assert record.page_count == 2
    assert len(engine.calls) == 1, "no trim on an in-budget CV"
    assert record.patch_json == patch.model_dump(mode="json"), "the no-trim patch is unchanged"


# --- the bound, exhaustion and the failed-trim fallback -------------------------


async def test_a_never_fitting_cv_stops_as_an_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Never Fits",
        patch=TailoringPatch(listing_id=1),
        outcomes=[9, 9, 9, 9, 9, 9, 9, 9],
    )

    assert record.compile_status == "ok", "a still-over-budget CV is downloadable, never blocked"
    assert record.page_count == 9
    assert len(engine.calls) <= MAX_PAGE_TRIM_PASSES + 1
    assert _check_status(record, "page_budget") == "warn"
    # The stand-in entry has three bullets: two drops, then a sole survivor stops it.
    assert len(record.patch_json["ops"]) == 2
    assert [op["op"] for op in record.patch_json["ops"]] == ["drop_bullet", "drop_bullet"]


async def test_the_trim_loop_respects_its_pass_bound(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(tailor_module, "MAX_PAGE_TRIM_PASSES", 1)
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Bound Hit",
        patch=TailoringPatch(listing_id=1),
        outcomes=[9, 9, 9],
    )

    assert record.compile_status == "ok"
    assert len(engine.calls) == 2, "one initial compile plus exactly the capped one trim"
    assert len(record.patch_json["ops"]) == 1


async def test_a_trim_recompile_failure_keeps_the_last_good_compile(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Trim Recompile Fails",
        patch=TailoringPatch(listing_id=1),
        outcomes=[3, None],
    )

    assert record.compile_status == "ok", "a failed trim must not fail the artifact"
    assert record.page_count == 3, "the last good compile is retained"
    assert len(engine.calls) == 2
    assert record.patch_json["ops"] == [], "the rejected trim is not persisted"


async def test_a_targeted_bullet_is_never_trimmed_twice(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch = TailoringPatch(
        listing_id=1,
        ops=[DropBullet(op="drop_bullet", bullet_id=BULLET3, reason="model already dropped it")],
    )
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Targeted Bullet",
        patch=patch,
        outcomes=[3, 2],
    )

    assert record.compile_status == "ok"
    assert len(engine.calls) == 2, "no InvalidPatchError from a duplicate target"
    dropped = {op["bullet_id"] for op in record.patch_json["ops"]}
    assert dropped == {BULLET3, BULLET2}
    assert len(record.patch_json["ops"]) == 2


async def test_a_sole_survivor_entry_stops_the_trim(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch = TailoringPatch(
        listing_id=1,
        ops=[
            DropBullet(op="drop_bullet", bullet_id=BULLET3, reason="model drop"),
            DropBullet(op="drop_bullet", bullet_id=BULLET2, reason="model drop"),
        ],
    )
    _, record, engine = await _compile(
        session_factory,
        tmp_path,
        monkeypatch,
        title="Sole Survivor",
        patch=patch,
        outcomes=[3, 3],
    )

    assert record.compile_status == "ok"
    assert record.page_count == 3
    assert len(engine.calls) == 1, "no candidate: the entry header would be orphaned"
    assert record.patch_json == patch.model_dump(mode="json")


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
