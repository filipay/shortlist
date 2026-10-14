"""TAIL-01 / TAIL-02 / TAIL-03 / D-108 (superseded) / D-111 / D-115 / D-118.

Observable truths a verifier should check:

1. `POST .../generate` on a scored listing returns a fragment containing a
   `patch_json` hidden field, writes zero `cv_artifacts` rows and zero `.tex` files,
   and keeps exactly one `cv_drafts` row per listing.
2. The page on an unscored listing renders the `rank first` state and no generate control.
3. A Layer-1 fail at compile writes exactly one `blocked` row with NULL paths.
4. A passing compile writes exactly one `ok` row with non-null paths and page count.
5. `GET .../pdf` returns 200 bytes for the `ok` row and 404 when only a blocked row exists.
"""

from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
import structlog
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.cv.factstore import load_facts
from app.db.models import CvArtifact, CvDraft, LlmCall
from app.domain.cv import BulletWeight, GapFinding, TailoringPatch, facts_hash
from app.latex.base import CompileResult, EngineProbe
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult
from app.pipeline import tailor as tailor_module
from tests.api.test_listing_detail import _register_sources, _seed_listing, _seed_scored_listing
from tests.verify.fixtures import FACTS_YAML, VERIFY_FIXTURES

PATCH_RE = re.compile(r'name="patch_json" value="([^"]*)"')
HIDDEN_RE = re.compile(r'name="(patch_json|base_cv_version_id|fact_store_hash)" value="([^"]*)"')


DEFAULT_PATCH = TailoringPatch(
    listing_id=1,
    ops=[
        BulletWeight(
            op="reweight_bullet",
            bullet_id="bul/northwind-labs-2021/1",
            weight=2.0,
        )
    ],
)


class TailoringStubBackend:
    """Returns one fixed valid patch and records the calls it received."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raise_transport = False
        self.patch = DEFAULT_PATCH

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
        if self.raise_transport:
            raise RuntimeError("backend transport down")
        return StructuredCallResult(
            ok=True, status="ok", data=self.patch, provider="opencode", model="minimax-m3"
        )


class StubEngine:
    """Writes a canned PDF and records the compiles it received."""

    def __init__(self, *, ok: bool = True) -> None:
        self.calls: list[str] = []
        self._ok = ok

    async def compile(self, *, tex: str, workdir: Path) -> CompileResult:
        self.calls.append(tex)
        workdir.mkdir(parents=True, exist_ok=True)
        if not self._ok:
            return CompileResult(ok=False, engine="stub", error="boom", error_kind="compile_error")
        pdf = workdir / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4 stub\n")
        return CompileResult(
            ok=True,
            engine="stub",
            pdf_path=str(pdf),
            page_count=1,
            tex_hash="a" * 64,
            pdf_hash="b" * 64,
            compile_log="ok",
        )

    async def health(self) -> EngineProbe:
        return EngineProbe(available=True)


_BACKEND = TailoringStubBackend()
_ENGINE = StubEngine()


@pytest.fixture(autouse=True)
def _reset_stubs() -> None:
    _BACKEND.calls.clear()
    _BACKEND.raise_transport = False
    _BACKEND.patch = DEFAULT_PATCH
    _ENGINE.calls.clear()


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
    # The stub engine writes a canned (non-pypdf-readable) PDF, so Layer-2 extraction
    # is stubbed to the committed pass fixture. The real extraction is exercised by the
    # container `latex` lane, never here.
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


async def _artifact_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[CvArtifact]:
    async with session_factory() as session:
        return list((await session.execute(select(CvArtifact))).scalars().all())


async def _llm_call_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[LlmCall]:
    async with session_factory() as session:
        return list((await session.execute(select(LlmCall))).scalars().all())


async def _draft_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[CvDraft]:
    async with session_factory() as session:
        return list((await session.execute(select(CvDraft))).scalars().all())


def _extract_patch(body: str) -> str:
    match = PATCH_RE.search(body)
    assert match is not None, "the review fragment must carry a patch_json hidden field"
    return html.unescape(match.group(1))


def _hidden_fields(body: str) -> dict[str, str]:
    """The three D-109 guard fields, as the compile route reads them."""
    return {match.group(1): html.unescape(match.group(2)) for match in HIDDEN_RE.finditer(body)}


# --- truth 2: the unscored page offers no generate control ---------------------


async def test_page_renders_rank_first_for_an_unscored_listing(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin")
    listing_id = await _seed_listing(session_factory, index=9, title="Unscored Role")

    response = await tailoring_client.get(f"/listings/{listing_id}/cv")

    assert response.status_code == 200
    body = response.text
    assert "Rank this listing first" in body
    assert "Generate tailored CV" not in body, "no generate control on an unscored listing"


# --- truth 1: generate returns the review fragment and keeps one draft ----------


async def test_generate_returns_the_review_fragment_and_persists_only_a_draft(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Tailoring Role")

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert response.status_code == 200
    body = response.text
    assert 'id="tailoring-review"' in body
    assert 'name="patch_json"' in body
    assert _extract_patch(body)
    assert await _artifact_rows(session_factory) == [], "generate persists no artifact row"
    drafts = await _draft_rows(session_factory)
    assert len(drafts) == 1, "generate keeps exactly one live draft"
    assert drafts[0].listing_id == listing_id
    assert drafts[0].patch_json == _BACKEND.patch.model_dump(mode="json")
    assert list((tmp_path / "artifacts").rglob("*.tex")) == [], "generate writes no .tex"
    assert len(_BACKEND.calls) == 1, "exactly one tailoring call per generate"


async def test_a_reload_reconnects_to_the_stored_draft(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The generated CV survives navigation: the page rebuilds it from the stored row."""
    listing_id = await _seed_scored_listing(session_factory, title="Reload Role")

    await tailoring_client.post(f"/listings/{listing_id}/cv/generate")
    assert len(await _draft_rows(session_factory)) == 1, "the draft is stored"

    body = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text

    assert 'id="tailoring-review"' in body
    assert "Tailored CV preview" in body, "the restored review shows the preview"
    assert "Change log" in body, "the restored review shows the change log"
    assert set(_hidden_fields(body)) == {
        "patch_json",
        "base_cv_version_id",
        "fact_store_hash",
    }, "the compile form's guard fields are restored from the stored draft"


async def test_regenerate_replaces_rather_than_accumulates(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Regenerate Role")

    await tailoring_client.post(f"/listings/{listing_id}/cv/generate")
    await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    drafts = await _draft_rows(session_factory)
    assert len(drafts) == 1, "a regenerate replaces the live draft, never accumulates"
    assert drafts[0].listing_id == listing_id


async def test_an_invalid_patch_persists_no_draft(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Invalid Patch Role")
    # An op referencing a fact ID the store does not carry makes `apply_patch` raise.
    _BACKEND.patch = TailoringPatch(
        listing_id=listing_id,
        ops=[
            BulletWeight(
                op="reweight_bullet",
                bullet_id="bul/does-not-exist/1",
                weight=2.0,
            )
        ],
    )

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert response.status_code == 502
    assert 'data-error="invalid-patch"' in response.text
    assert await _artifact_rows(session_factory) == []
    assert await _draft_rows(session_factory) == [], "an invalid patch is never persisted"


async def test_an_invalid_patch_emits_exactly_one_refusal_warning(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The refusal is observable: one warning carrying the class and the offending id.

    ``InvalidPatchError`` means the id-grounding step PASSED and the schema was valid
    — the model produced a self-conflicting op set, which this phase refuses rather
    than repairs (D-118). Without this event the live failure is undiagnosable, so the
    test pins the payload to the exception class AND the identifier from ``str(exc)``.
    The literal repro is two mutating ops on the same real bullet id.
    """
    listing_id = await _seed_scored_listing(session_factory, title="Conflict Role")
    bullet_id = "bul/northwind-labs-2021/1"
    _BACKEND.patch = TailoringPatch(
        listing_id=listing_id,
        ops=[
            BulletWeight(op="reweight_bullet", bullet_id=bullet_id, weight=1.0),
            BulletWeight(op="reweight_bullet", bullet_id=bullet_id, weight=2.0),
        ],
    )

    with structlog.testing.capture_logs() as events:
        response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    # The user-facing refusal is byte-identical to the pre-fix response.
    assert response.status_code == 502
    assert response.text == (
        '<div id="tailoring-review" class="tailoring-empty" '
        'data-error="invalid-patch">'
        "The model proposed an invalid change (InvalidPatchError).</div>"
    )

    warnings = [entry for entry in events if entry.get("event") == "tailoring.patch_refused"]
    assert len(warnings) == 1, "exactly one refusal warning"
    assert warnings[0]["log_level"] == "warning"
    assert warnings[0]["error"] == "InvalidPatchError"
    assert warnings[0]["listing_id"] == listing_id
    assert bullet_id in warnings[0]["detail"], "the offending id survives to the log"


async def test_a_successful_generate_emits_no_refusal_warning(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Negative control: the refusal warning fires only on the refused path."""
    listing_id = await _seed_scored_listing(session_factory, title="Clean Role")

    with structlog.testing.capture_logs() as events:
        response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert response.status_code == 200
    assert [entry for entry in events if entry.get("event") == "tailoring.patch_refused"] == []


async def test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """WR-01: a raised transport error is a typed 502 refusal with one audit row, never a 500."""
    listing_id = await _seed_scored_listing(session_factory, title="Raising Role")
    _BACKEND.raise_transport = True

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")

    assert response.status_code == 502, "a raised backend error must not escape as a 500"
    assert 'data-error="tailoring_failed"' in response.text
    assert len(_BACKEND.calls) == 1, "the call was attempted and observable"

    rows = await _llm_call_rows(session_factory)
    assert len(rows) == 1, "exactly one audit row for the attempted call"
    assert rows[0].purpose == "tailor"
    assert rows[0].status == "error"
    assert rows[0].run_id is None
    assert rows[0].error == "RuntimeError", "the class only, never the message"


# --- truth 4: a passing compile writes one ok row ------------------------------


async def test_compile_writes_one_ok_row_and_the_page_offers_the_download(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Compiling Role")

    generated = await tailoring_client.post(f"/listings/{listing_id}/cv/generate")
    fields = _hidden_fields(generated.text)

    response = await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    assert response.status_code == 200
    assert "Compiled." in response.text
    assert '<a class="cv-download"' not in response.text, (
        "the banner does not duplicate the persistent Latest CV control"
    )
    # The single download control lives on the page the swap leaves in place.
    page = (await tailoring_client.get(f"/listings/{listing_id}/cv")).text
    assert f'href="/listings/{listing_id}/cv/pdf"' in page, "the page offers the download"

    rows = await _artifact_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].compile_status == "ok"
    assert rows[0].tex_path is not None
    assert rows[0].pdf_path is not None
    assert rows[0].page_count == 1
    assert len(list((tmp_path / "artifacts").rglob("*.tex"))) == 1
    assert len(_ENGINE.calls) == 1


# --- truth 3 + 5: a Layer-1 fail blocks, writes no PDF and is unreachable -------


async def test_compile_short_circuits_a_layer_one_fail_to_a_blocked_row(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Blocked Role")
    # A `direct` finding with no evidence id fails requirement_evidence at Layer 1.
    blocked_patch = TailoringPatch(
        listing_id=listing_id,
        gaps=[GapFinding(requirement="Rust", status="direct", evidence_ids=[])],
    )

    response = await tailoring_client.post(
        f"/listings/{listing_id}/cv/compile",
        data={
            "patch_json": blocked_patch.model_dump_json(),
            "fact_store_hash": facts_hash(load_facts(FACTS_YAML)),
        },
    )

    assert response.status_code == 200
    assert 'data-status="blocked"' in response.text

    rows = await _artifact_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].compile_status == "blocked"
    assert rows[0].tex_path is None
    assert rows[0].pdf_path is None
    assert rows[0].verification_json, "a blocked row carries its findings"
    assert _ENGINE.calls == [], "a Layer-1 fail must never reach the engine"

    # Truth 5: the PDF route cannot serve a blocked artifact (D-118).
    pdf = await tailoring_client.get(f"/listings/{listing_id}/cv/pdf")
    assert pdf.status_code == 404


# --- truth 5: the ok artifact is served as bytes -------------------------------


async def test_the_pdf_route_serves_the_ok_artifact(
    tailoring_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_scored_listing(session_factory, title="Served Role")
    fields = _hidden_fields(
        (await tailoring_client.post(f"/listings/{listing_id}/cv/generate")).text
    )
    await tailoring_client.post(f"/listings/{listing_id}/cv/compile", data=fields)

    response = await tailoring_client.get(f"/listings/{listing_id}/cv/pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
