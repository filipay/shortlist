"""TAIL-07 / TAIL-08 / D-107..D-110 — the review step and the stale-patch guard.

Observable truths a verifier should check:

1. An unscored listing's tailoring page renders the rank-first state and no generate
   control; a scored listing renders the generate control.
2. A blocked artifact renders the blocked state and no download link; an `ok` artifact
   renders the download affordance.
3. `POST .../generate` returns the preview beside the change log and the three guard
   fields, writes zero `cv_artifacts` rows and no `.tex`/`.pdf`, and keeps one
   `cv_drafts` row; `POST .../delete` removes that row and redirects to the page.
4. A drop and a demotion are each listed with their reason, and a declared drop is shown
   struck in the preview rather than omitted (TAIL-08).
5. `POST .../compile` with a mutated `fact_store_hash` or a moved `base_cv_version_id`
   returns 409 `data-error="stale-patch"` and writes no row; a malformed `patch_json` is
   refused; an intact guard compiles exactly one `ok` row.
"""

from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import CvArtifact, CvDraft
from app.db.repositories import cv_artifact_repo, cv_repo
from app.db.repositories.cv_artifact_repo import CvArtifactRecord
from app.domain.cv import (
    PAGE_TRIM_REASON_TEMPLATE,
    BulletWeight,
    DemoteBullet,
    DropBullet,
    GapFinding,
    Suggestion,
    TailoringPatch,
)
from app.latex.base import CompileResult, EngineProbe
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult
from app.pipeline import tailor as tailor_module
from tests.api.test_listing_detail import _register_sources, _seed_listing, _seed_scored_listing
from tests.verify.fixtures import FACTS_YAML, VERIFY_FIXTURES

NOW = datetime(2026, 9, 24, tzinfo=UTC)

BULLET1 = "bul/northwind-labs-2021/1"
BULLET2 = "bul/northwind-labs-2021/2"
BULLET3 = "bul/northwind-labs-2021/3"

HIDDEN_RE = re.compile(r'name="(patch_json|base_cv_version_id|fact_store_hash)" value="([^"]*)"')

#: One requirement-coverage row: its class, status and requirement text.
REQ_ROW_RE = re.compile(r'<li class="(req-[a-z]+)">\s*<strong>([^<]+)</strong> — ([^<\n]+)', re.S)


class ReviewStubBackend:
    """Returns the current `patch` and records the calls it received."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.patch = TailoringPatch(listing_id=1)

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
        self.calls.append({"system": system, "text": "\n".join(parts)})
        return StructuredCallResult(
            ok=True, status="ok", data=self.patch, provider="opencode", model="minimax-m3"
        )


class StubEngine:
    """Writes a canned PDF and records the compiles it received."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        #: Optional per-compile page counts, popped in order; empty means page_count 1.
        self.page_counts: list[int] = []

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        self.calls.append(tex)
        workdir.mkdir(parents=True, exist_ok=True)
        pdf = workdir / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4 stub\n")
        page_count = self.page_counts.pop(0) if self.page_counts else 1
        return CompileResult(
            ok=True,
            engine="stub",
            pdf_path=str(pdf),
            page_count=page_count,
            tex_hash="a" * 64,
            pdf_hash="b" * 64,
            compile_log="ok",
        )

    async def health(self) -> EngineProbe:
        return EngineProbe(available=True)


_BACKEND = ReviewStubBackend()
_ENGINE = StubEngine()


@pytest.fixture(autouse=True)
def _reset_stubs() -> None:
    _BACKEND.calls.clear()
    _BACKEND.patch = TailoringPatch(listing_id=1)
    _ENGINE.calls.clear()
    _ENGINE.page_counts.clear()


@pytest_asyncio.fixture
async def tailoring_client(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AsyncIterator[AsyncClient]:
    from app.db.session import get_session, get_session_factory
    from app.latex import get_latex_engine
    from app.llm import get_llm_backend
    from app.main import create_app

    cv_dir = tmp_path / "cv"
    cv_dir.mkdir(parents=True, exist_ok=True)
    (cv_dir / "cv.yaml").write_text(FACTS_YAML.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(cv_dir))
    monkeypatch.setattr(settings, "artifacts_dir", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        tailor_module,
        "extract_pdf_text",
        lambda path: (VERIFY_FIXTURES / "base_extract.txt").read_text(encoding="utf-8"),
    )

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_llm_backend] = lambda: _BACKEND
    app.dependency_overrides[get_latex_engine] = lambda: _ENGINE

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    app.dependency_overrides.clear()


def _hidden_fields(body: str) -> dict[str, str]:
    return {match.group(1): html.unescape(match.group(2)) for match in HIDDEN_RE.finditer(body)}


async def _artifact_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[CvArtifact]:
    async with session_factory() as session:
        return list((await session.execute(select(CvArtifact))).scalars().all())


async def _draft_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[CvDraft]:
    async with session_factory() as session:
        return list((await session.execute(select(CvDraft))).scalars().all())


async def _seed_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    compile_status: str,
    pdf_path: str | None = None,
) -> None:
    async with session_factory() as session:
        await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={"listing_id": listing_id},
            change_log_json=[],
            compile_status=compile_status,
            verification_json={"passed": compile_status == "ok"},
            page_count=1 if compile_status == "ok" else None,
            tex_path="/tmp/cv.tex" if pdf_path else None,
            pdf_path=pdf_path,
            now=NOW,
        )
        await session.commit()


# --- Task 1: the page states ---------------------------------------------------


async def test_an_unscored_listing_shows_rank_first_and_no_generate_control(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=9, title="Unscored Role")

    body = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text

    assert "Rank this listing first" in body
    assert 'data-state="rank_first"' in body
    assert "Generate tailored CV" not in body, "no generate control on an unscored listing"


async def test_a_scored_listing_shows_the_generate_control(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Scored Role")

    body = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text

    assert "Generate tailored CV" in body
    assert 'id="tailoring-review"' in body


async def test_a_blocked_artifact_shows_blocked_and_no_download(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Blocked State Role")
    await _seed_artifact(session_factory, listing_id=listing_id, compile_status="blocked")

    body = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text

    assert "Status: blocked" in body
    assert "/cv/pdf" not in body, "a blocked artifact is not downloadable"


async def test_an_ok_artifact_shows_the_download_affordance(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Ok State Role")
    await _seed_artifact(
        session_factory, listing_id=listing_id, compile_status="ok", pdf_path="/tmp/cv.pdf"
    )

    body = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text

    assert "Status: ok" in body
    assert f"/listings/{listing_id}/cv/pdf" in body
    assert "Download PDF" in body


async def test_the_detail_page_links_to_the_tailoring_page(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Linked Role")

    body = (await client.get(f"/listings/{listing_id}")).text

    assert f'href="/listings/{listing_id}/cv"' in body
    assert "Tailor my CV for this job" in body


# --- Task 2: the review fragment -----------------------------------------------


async def test_generate_returns_the_review_fragment_with_preview_and_guard_fields(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Review Role")

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert response.status_code == 200
    body = response.text
    assert 'id="tailoring-review"' in body
    assert "Tailored CV preview" in body
    assert "Change log" in body
    fields = _hidden_fields(body)
    assert set(fields) == {"patch_json", "base_cv_version_id", "fact_store_hash"}
    assert await _artifact_rows(session_factory) == [], "generate persists no artifact row"
    assert list((tmp_path / "artifacts").rglob("*.tex")) == [], "generate writes no .tex"


async def test_generate_persists_a_draft_not_an_artifact(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="No Artifact Role")

    await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert await _artifact_rows(session_factory) == []
    drafts = await _draft_rows(session_factory)
    assert len(drafts) == 1
    assert drafts[0].listing_id == listing_id


async def test_delete_removes_the_draft_and_redirects_to_the_page(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The explicit delete is the only removal path, and it 303s a plain form back."""
    listing_id = await _seed_scored_listing(session_factory, title="Delete Role")
    await tailoring_client.post(f"/listings/{listing_id}/cv/generate")
    assert len(await _draft_rows(session_factory)) == 1

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/delete")

    assert response.status_code == 303
    assert response.headers["location"] == f"/listings/{listing_id}/cv"
    assert await _draft_rows(session_factory) == [], "the draft row is gone"
    assert await _artifact_rows(session_factory) == [], "delete touches no artifact"

    body = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text
    assert "Tailored CV preview" not in body, "the page no longer shows the deleted draft"
    assert 'name="patch_json"' not in body


async def test_delete_of_an_unknown_listing_is_a_404_fragment(
    tailoring_client: AsyncClient,
) -> None:
    response = await tailoring_client.post("/listings/9999/cv/delete")

    assert response.status_code == 404
    assert "unknown-listing" in response.text


async def test_a_dropped_bullet_is_struck_and_listed_with_its_reason(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Drop Role")
    _BACKEND.patch = TailoringPatch(
        listing_id=listing_id,
        ops=[DropBullet(op="drop_bullet", bullet_id=BULLET2, reason="Not relevant to this role")],
    )

    body = (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text

    assert "<s>Led the migration to a single-writer queue</s>" in body, "the drop is struck"
    assert "Not relevant to this role" in body
    assert "drop_bullet" in body


async def test_a_demoted_bullet_is_listed_with_its_reason(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Demote Role")
    _BACKEND.patch = TailoringPatch(
        listing_id=listing_id,
        ops=[DemoteBullet(op="demote_bullet", bullet_id=BULLET3, reason="Keep this secondary")],
    )

    body = (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text

    assert "Keep this secondary" in body
    assert "demote_bullet" in body


async def test_the_requirement_and_suggestion_panels_render(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Panels Role")
    _BACKEND.patch = TailoringPatch(
        listing_id=listing_id,
        ops=[BulletWeight(op="reweight_bullet", bullet_id=BULLET1, weight=2.0)],
        gaps=[GapFinding(requirement="Kubernetes orchestration", status="gap")],
        suggestions=[
            Suggestion(bullet_id=BULLET1, evidence_ids=[], rationale="Add a summary line")
        ],
    )

    body = (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text

    assert "Kubernetes orchestration" in body
    assert "req-gap" in body
    assert "Add a summary line" in body
    assert "Suggestions (not applied to the render)" in body


async def test_requirement_rows_read_gap_then_partial_then_met(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The coverage panel sorts gap → partial → met, stable within a status.

    ``direct`` is the "met" status and ``adjacent``/``transferable`` are the "partial"
    ones (``app.domain.cv.GapFinding``); the deliberately shuffled input proves the
    panel does not simply echo ``patch.gaps``. Two ``gap`` rows pin the stability: the
    equal-severity pair keeps its input order.
    """
    listing_id = await _seed_scored_listing(session_factory, title="Ordered Coverage Role")
    _BACKEND.patch = TailoringPatch(
        listing_id=listing_id,
        gaps=[
            GapFinding(
                requirement="Direct requirement", status="direct", evidence_ids=["skill.python"]
            ),
            GapFinding(requirement="Gap one", status="gap"),
            GapFinding(
                requirement="Adjacent requirement",
                status="adjacent",
                evidence_ids=["skill.python"],
            ),
            GapFinding(
                requirement="Transferable requirement",
                status="transferable",
                evidence_ids=["skill.python"],
            ),
            GapFinding(requirement="Gap two", status="gap"),
        ],
    )

    body = (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text

    section = body.split("<h4>Requirement coverage</h4>", 1)[1].split("</ul>", 1)[0]
    rows = [(m.group(1), m.group(3).strip()) for m in REQ_ROW_RE.finditer(section)]
    assert [requirement for _, requirement in rows] == [
        "Gap one",
        "Gap two",
        "Adjacent requirement",
        "Transferable requirement",
        "Direct requirement",
    ], "gap → partial → met, stable within a status"
    assert [css for css, _ in rows] == [
        "req-gap",
        "req-gap",
        "req-partial",
        "req-partial",
        "req-met",
    ]


async def test_generate_on_an_unscored_listing_refuses_without_a_backend_call(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=17, title="Unscored Generate Role")

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert response.status_code == 422
    assert "no_score" in response.text
    assert _BACKEND.calls == [], "the refusal must precede any LLM call"


# --- Task 3: the stale-patch guard ---------------------------------------------


async def test_a_stale_fact_store_refuses_the_compile_and_writes_no_row(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Stale Hash Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )
    fields["fact_store_hash"] = "0" * 64

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 409
    assert 'data-error="stale-patch"' in response.text
    assert "Generate a fresh tailoring" in response.text
    assert 'name="patch_json"' not in response.text, "no control may retry the stale patch"
    assert await _artifact_rows(session_factory) == []
    assert _ENGINE.calls == [], "a stale refusal never reaches the engine"


async def test_a_moved_cv_version_refuses_the_compile(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Moved Version Role")
    async with session_factory() as session:
        await cv_repo.snapshot_version(
            session, facts_json={"schema_version": 1}, schema_version=1, source="hand"
        )
        await session.commit()

    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )
    assert fields["base_cv_version_id"] == "1"

    # A second revision lands between generate and compile.
    async with session_factory() as session:
        await cv_repo.snapshot_version(
            session, facts_json={"schema_version": 1}, schema_version=1, source="hand"
        )
        await session.commit()

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 409
    assert 'data-error="stale-patch"' in response.text
    assert await _artifact_rows(session_factory) == []


async def test_a_malformed_patch_json_is_refused(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Malformed Patch Role")

    response = await tailoring_client.post(
        f"/listings/{listing_id}/cv/compile",
        data={"patch_json": "{not valid json", "fact_store_hash": "x"},
    )

    assert response.status_code == 422
    assert await _artifact_rows(session_factory) == []


async def test_an_intact_guard_compiles_and_writes_exactly_one_row(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Intact Guard Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 200
    rows = await _artifact_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].compile_status == "ok"
    assert rows[0].base_cv_version_id is None


# --- WR-01: the compile route honours the operator off switch -------------------


async def test_the_compile_route_refuses_when_tailoring_is_disabled(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """WR-01: a round-tripped patch POSTed at compile cannot render/compile/persist while off.

    The switch is turned off AFTER a valid generate captured the guard fields, so this
    is exactly the bypass the verifier reported: the fields are genuine, the route is
    the only thing that must refuse. The refusal must precede ``load_facts``, the
    render, the engine call and the insert.
    """
    listing_id = await _seed_scored_listing(session_factory, title="Disabled Compile Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )

    monkeypatch.setattr(settings, "tailoring_enabled", False)
    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 409
    assert 'data-error="tailoring_disabled"' in response.text
    assert await _artifact_rows(session_factory) == []
    assert list((tmp_path / "artifacts").rglob("*")) == [], "no file is written while disabled"
    assert _ENGINE.calls == [], "a disabled refusal never reaches the engine"


async def test_the_disabled_switch_is_honoured_across_the_tailoring_surfaces(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documented contract on every NEW-work surface: zero backend calls, zero rows.

    A listing is scored and a valid patch is captured while the switch is on, so the
    only variable is the switch. The page, the generate route and the compile route
    must all refuse with the same vocabulary and perform no work.
    """
    listing_id = await _seed_scored_listing(session_factory, title="Disabled Surfaces Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )
    _BACKEND.calls.clear()  # isolate the disabled-surface calls below

    monkeypatch.setattr(settings, "tailoring_enabled", False)

    page = await tailoring_client.get(f"/listings/{listing_id}/cv")
    assert page.status_code == 200
    assert 'data-state="tailoring_disabled"' in page.text
    assert tailor_module.TAILOR_SKIP_LABELS[tailor_module.TAILOR_SKIP_DISABLED] in page.text
    assert "Generate tailored CV" not in page.text, "no generate control while disabled"
    assert f"/listings/{listing_id}/cv/pdf" not in page.text, "no download link while disabled"

    generate = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")
    assert generate.status_code == 409
    assert 'data-error="tailoring_disabled"' in generate.text
    assert _BACKEND.calls == [], "a disabled generate precedes any LLM call"

    compile_response = await tailoring_client.post(
        f"/listings/{listing_id}/cv/compile", data=fields
    )
    assert compile_response.status_code == 409
    assert 'data-error="tailoring_disabled"' in compile_response.text
    assert await _artifact_rows(session_factory) == []


async def test_the_disabled_switch_is_not_a_one_way_trip(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard reads the LIVE setting: re-enabling restores the route on the same fields."""
    listing_id = await _seed_scored_listing(session_factory, title="Live Switch Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )

    monkeypatch.setattr(settings, "tailoring_enabled", False)
    refused = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)
    assert refused.status_code == 409
    assert 'data-error="tailoring_disabled"' in refused.text
    assert await _artifact_rows(session_factory) == []

    # The SAME round-tripped fields, with the switch restored: a real compile.
    monkeypatch.setattr(settings, "tailoring_enabled", True)
    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 200
    rows = await _artifact_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].compile_status == "ok"


# --- 260929-pan: the compile response discloses every page trim ----------------


def _record(change_log: list[dict[str, str]]) -> CvArtifactRecord:
    return CvArtifactRecord(
        id=7,
        listing_id=42,
        base_cv_version_id=None,
        patch_json={},
        change_log_json=change_log,
        tex_path="/tmp/cv.tex",
        pdf_path="/tmp/cv.pdf",
        tex_hash=None,
        pdf_hash=None,
        compiled_at=NOW,
        compile_status="ok",
        compile_log=None,
        verification_json={"passed": True},
        page_count=2,
        ats_checks_json=None,
        backend="opencode_server",
        provider=None,
        model=None,
        created_at=NOW,
    )


def test_compiled_fragment_names_every_drop_and_ignores_other_ops() -> None:
    from app.api.tailoring import _compiled_fragment

    reason = PAGE_TRIM_REASON_TEMPLATE.format(limit=2)
    body = _compiled_fragment(
        42,
        _record(
            [
                {"op": "drop_bullet", "target_id": "bul/x/3", "detail": reason},
                {"op": "reweight_bullet", "target_id": "bul/x/1", "detail": "2.0"},
                {"op": "drop_bullet", "target_id": "bul/x/2", "detail": reason},
            ]
        ),
    )

    assert 'data-status="ok"' in body
    assert 'href="/listings/42/cv/pdf"' in body
    assert "bul/x/3" in body
    assert "bul/x/2" in body, "not only the first drop is disclosed"
    assert body.count(reason) == 2
    assert "bul/x/1" not in body, "a non-drop change is not shown as a trim"


def test_compiled_fragment_with_no_drops_is_the_unchanged_download_fragment() -> None:
    from app.api.tailoring import _compiled_fragment

    body = _compiled_fragment(42, _record([]))

    assert 'data-status="ok"' in body
    assert "Compiled." in body
    assert 'href="/listings/42/cv/pdf"' in body
    assert "Download PDF" in body
    assert "page-trims" not in body


async def test_the_compile_response_names_every_page_trim(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Trim Disclosure Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )
    # Three page counts for three compiles: over budget, over budget, still over.
    _ENGINE.page_counts = [5, 4, 3]

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 200
    body = response.text
    assert 'data-status="ok"' in body
    rows = await _artifact_rows(session_factory)
    assert rows[0].compile_status == "ok"
    assert rows[0].page_count == 3
    assert BULLET3 in body, "the first trimmed bullet is named"
    assert BULLET2 in body, "the second trimmed bullet is named"
    reason = PAGE_TRIM_REASON_TEMPLATE.format(limit=2)
    assert body.count(reason) == 2


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
