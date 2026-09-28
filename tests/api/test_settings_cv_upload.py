"""POST /settings/cv converts a submitted LaTeX CV into the live fact store.

The route is a plain urlencoded POST (no python-multipart). Everything here is
asserted on observable behavior: files on disk and the rendered response, never a
private helper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Sequence
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.cv.factstore import load_facts
from app.cv.llm_extract import (
    _ExtractedCv,
    _ExtractedEntry,
    _ExtractedMeta,
    _ExtractedSection,
)
from app.llm.base import DiscoveryResult, ProbeOutcome, StructuredCallResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALID_TEX = (PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.tex").read_text(
    encoding="utf-8"
)

#: A document the bounded parser handles completely (no unresolved macro/heading),
#: so the deterministic fast path runs and the model must not be called.
PARSER_CLEAN_TEX = r"""\documentclass{article}
\newcommand{\cvrole}[3]{\textbf{#1} --- \textit{#2} \hfill #3}
\begin{document}
\section{Experience}
\cvrole{Northwind Labs}{Senior Engineer}{2021-03 -- 2024-09}
\begin{itemize}
\item Led the migration
\end{itemize}
\end{document}
"""

#: A real-world-shaped document: a title-first custom entry macro, a highlights
#: environment passed as the 4th argument, non-standard headings, bare-year and
#: ``present`` dates, and a ``\LARGE \textbf{...}`` name header.
REAL_TEX = r"""\documentclass{article}
\newcommand{\workentry}[4]{\textbf{#1} \textit{#2} \hfill #3 #4}
\begin{document}
\begin{center}{\LARGE \textbf{Alex Example}}\\ alex@example.invalid\end{center}
\section*{WORK EXPERIENCE}
\workentry{Senior Backend Engineer}{Northwind Labs}{2021 - 2023}{%
\begin{highlights}\item Built the ingest path\end{highlights}}
\workentry{Platform Engineer}{Acme Corp}{2026 - present}{%
\begin{highlights}\item Owned the deploy pipeline\end{highlights}}
\section*{PROJECTS}
\workentry{Lead Developer}{Widget Kit}{2026}{%
\begin{highlights}\item Shipped v1\end{highlights}}
\section*{EDUCATION}
\workentry{BSc Computer Science}{Trinity College}{2024}{%
\begin{highlights}\item First class honours\end{highlights}}
\section*{VOLUNTEERING}
\workentry{Mentor}{Code Club}{2021 - 2023}{%
\begin{highlights}\item Mentored students\end{highlights}}
\section*{CODING PROFICIENCY}
Python, Go, SQL
\end{document}
"""


def _real_extraction() -> _ExtractedCv:
    return _ExtractedCv(
        meta=_ExtractedMeta(name="Alex Example", email="alex@example.invalid"),
        sections=[
            _ExtractedSection(
                heading="WORK EXPERIENCE",
                entries=[
                    _ExtractedEntry(
                        org="Northwind Labs",
                        title="Senior Backend Engineer",
                        dates="2021 - 2023",
                        bullets=["Built the ingest path"],
                    ),
                    _ExtractedEntry(
                        org="Acme Corp",
                        title="Platform Engineer",
                        dates="2026 - present",
                        bullets=["Owned the deploy pipeline"],
                    ),
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="PROJECTS",
                entries=[
                    _ExtractedEntry(
                        org="Widget Kit",
                        title="Lead Developer",
                        dates="2026",
                        bullets=["Shipped v1"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="EDUCATION",
                entries=[
                    _ExtractedEntry(
                        org="Trinity College",
                        title="BSc Computer Science",
                        dates="2024",
                        bullets=["First class honours"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="VOLUNTEERING",
                entries=[
                    _ExtractedEntry(
                        org="Code Club",
                        title="Mentor",
                        dates="2021 - 2023",
                        bullets=["Mentored students"],
                    )
                ],
                skills=[],
            ),
            _ExtractedSection(
                heading="CODING PROFICIENCY", entries=[], skills=["Python", "Go", "SQL"]
            ),
        ],
    )


class CvStubBackend:
    """A canned extraction (or a failure) that records the calls it received."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.extracted: _ExtractedCv | None = None
        self.raise_transport = False
        self.ok = True
        self.error: str | None = None

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
        self.calls.append({"schema": schema, "system": system, "text": "\n".join(parts)})
        if self.raise_transport:
            raise RuntimeError("backend transport down")
        if not self.ok:
            return StructuredCallResult(ok=False, status="invalid", error=self.error)
        return StructuredCallResult(ok=True, status="ok", data=self.extracted)


_BACKEND = CvStubBackend()


@pytest.fixture(autouse=True)
def _reset_backend() -> Iterator[None]:
    _BACKEND.calls.clear()
    _BACKEND.extracted = None
    _BACKEND.raise_transport = False
    _BACKEND.ok = True
    _BACKEND.error = None
    yield


@pytest_asyncio.fixture
async def cv_client(
    session_factory: async_sessionmaker[AsyncSession], cv_dir: Path
) -> AsyncIterator[AsyncClient]:
    """The settings client with the LLM backend overridden by `_BACKEND`."""
    from app.db.session import get_session, get_session_factory
    from app.llm import get_llm_backend
    from app.main import create_app

    app = create_app()

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_llm_backend] = lambda: _BACKEND

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    app.dependency_overrides.clear()


#: A document the bounded parser recognises (one real section) but whose entry macro
#: call carries no parseable date, so the converted draft fails ``load_facts``.
INVALID_TEX = r"""
\documentclass{article}
\newcommand{\cventry}[3]{#1 #2 #3}
\begin{document}
\section{Experience}
\cventry{Acme}{Engineer}{sometime}
\end{document}
"""

OLD_STORE = "schema_version: 1\nmeta: {}\nsections: []\n"


@pytest.fixture
def cv_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A dedicated, isolated CV directory (the test DB also lives under `tmp_path`)."""
    path = tmp_path / "cv"
    path.mkdir()
    monkeypatch.setattr(settings, "cv_dir", str(path))
    yield path


@pytest.mark.parametrize("payload", ["", "   \n\t ", "this is not a CV at all"])
async def test_empty_or_garbage_tex_reports_an_error_and_changes_nothing(
    client, cv_dir: Path, payload: str
) -> None:
    existing = cv_dir / "cv.yaml"
    existing.write_text(OLD_STORE, encoding="utf-8")

    response = await client.post("/settings/cv", data={"cv_tex": payload})

    assert response.status_code == 200
    assert 'data-status="error"' in response.text
    assert "Not saved" in response.text
    assert existing.read_text(encoding="utf-8") == OLD_STORE
    assert sorted(path.name for path in cv_dir.iterdir()) == ["cv.yaml"]


async def test_a_valid_tex_is_converted_validated_and_published(
    client, cv_dir: Path
) -> None:
    response = await client.post("/settings/cv", data={"cv_tex": VALID_TEX})

    assert response.status_code == 200
    target = cv_dir / "cv.yaml"
    assert target.exists()
    # The published file is loadable by the SAME loader ranking/tailoring use.
    facts = load_facts(target)
    assert len(facts.sections) == 2
    assert 'data-status="ok"' in response.text
    assert "Saved" in response.text
    assert "entries parsed: 1" in response.text
    assert "stale" in response.text


async def test_a_draft_with_no_parsable_entry_leaves_the_store_and_no_temp_file(
    client, cv_dir: Path
) -> None:
    """A recognised section whose entry has no parseable date.

    The converted draft would carry an entry with no ``id``/``start`` — not a
    usable fact — so the request is refused before anything is written. The
    store is untouched and no validation temp file is left behind.
    """
    existing = cv_dir / "cv.yaml"
    existing.write_text(OLD_STORE, encoding="utf-8")

    response = await client.post("/settings/cv", data={"cv_tex": INVALID_TEX})

    assert response.status_code == 200
    assert 'data-status="error"' in response.text
    assert "Not saved" in response.text
    assert existing.read_text(encoding="utf-8") == OLD_STORE
    # The temp file written for validation must be gone; only the store remains.
    assert sorted(path.name for path in cv_dir.iterdir()) == ["cv.yaml"]


async def test_a_recognised_section_with_no_entries_leaves_the_store_untouched(
    client, cv_dir: Path
) -> None:
    """The second half of "no usable content": a section but nothing in it.

    ``load_facts`` accepts a store with zero entries, so without the explicit
    ``entries_parsed`` gate this would replace the live CV with an empty one.
    """
    existing = cv_dir / "cv.yaml"
    existing.write_text(OLD_STORE, encoding="utf-8")
    heading_only = "\\section{Experience}\n"

    response = await client.post("/settings/cv", data={"cv_tex": heading_only})

    assert response.status_code == 200
    assert 'data-status="error"' in response.text
    assert existing.read_text(encoding="utf-8") == OLD_STORE
    assert sorted(path.name for path in cv_dir.iterdir()) == ["cv.yaml"]


async def test_an_existing_store_is_backed_up_before_it_is_replaced(
    client, cv_dir: Path
) -> None:
    existing = cv_dir / "cv.yaml"
    existing.write_text(OLD_STORE, encoding="utf-8")

    response = await client.post("/settings/cv", data={"cv_tex": VALID_TEX})

    assert response.status_code == 200
    assert 'data-status="ok"' in response.text
    assert (cv_dir / "cv.yaml.bak").read_text(encoding="utf-8") == OLD_STORE
    assert load_facts(cv_dir / "cv.yaml").schema_version == 1


# --- the hybrid path: deterministic first, model-assisted when needed ----------


async def test_a_real_shaped_tex_is_imported_with_model_assistance(
    cv_client, cv_dir: Path
) -> None:
    """A custom macro + non-standard headings import through the model path."""
    _BACKEND.extracted = _real_extraction()

    response = await cv_client.post("/settings/cv", data={"cv_tex": REAL_TEX})

    assert response.status_code == 200
    assert 'data-status="ok"' in response.text
    target = cv_dir / "cv.yaml"
    assert target.exists()
    facts = load_facts(target)
    assert len(facts.sections) >= 2
    assert facts.all_entries(), "the saved store must carry at least one entry"
    assert "model assistance" in response.text
    assert len(_BACKEND.calls) == 1


async def test_model_assistance_is_not_used_when_the_parser_succeeds(
    cv_client, cv_dir: Path
) -> None:
    """The fast path: a fully-parsed document must never spend a model call.

    A dedicated parser-clean document is used because the committed fixture is
    macro-heavy by design and the mandated ``needs_help`` formula counts its
    unresolved preamble macros as "needs help" (that case is covered below).
    """
    _BACKEND.raise_transport = True

    response = await cv_client.post("/settings/cv", data={"cv_tex": PARSER_CLEAN_TEX})

    assert response.status_code == 200
    assert 'data-status="ok"' in response.text
    assert _BACKEND.calls == [], "the deterministic fast path must not call the model"
    facts = load_facts(cv_dir / "cv.yaml")
    assert facts.all_entries()
    assert "parsed directly from the LaTeX" in response.text


async def test_a_model_failure_falls_back_to_the_deterministic_store(
    cv_client, cv_dir: Path
) -> None:
    """A partial deterministic parse survives a failing model pass."""
    _BACKEND.raise_transport = True

    response = await cv_client.post("/settings/cv", data={"cv_tex": VALID_TEX})

    assert response.status_code == 200
    assert 'data-status="ok"' in response.text
    facts = load_facts(cv_dir / "cv.yaml")
    assert facts.all_entries()
    assert "model-assisted pass failed" in response.text
    assert "kept the deterministic result" in response.text


async def test_a_model_failure_with_nothing_parsable_leaves_the_store_untouched(
    cv_client, cv_dir: Path
) -> None:
    """Neither path can do the job: the existing store is byte-identical."""
    existing = cv_dir / "cv.yaml"
    existing.write_text(OLD_STORE, encoding="utf-8")
    _BACKEND.raise_transport = True

    response = await cv_client.post("/settings/cv", data={"cv_tex": INVALID_TEX})

    assert response.status_code == 200
    assert 'data-status="error"' in response.text
    assert existing.read_text(encoding="utf-8") == OLD_STORE
    # No leftover validation temp file from either attempt.
    assert sorted(path.name for path in cv_dir.iterdir()) == ["cv.yaml"]


async def test_the_model_schema_is_the_contract(cv_client, cv_dir: Path) -> None:
    """The route passes the `.tex` to the model and does not bypass the guard.

    A fabricated entry (its org absent from the source) is dropped by
    `llm_extract`'s grounding guard and never reaches the store.
    """
    extraction = _real_extraction()
    extraction.sections[0].entries.append(
        _ExtractedEntry(
            org="Ghost Corp", title="Invented Role", dates="2026", bullets=["fabricated"]
        )
    )
    _BACKEND.extracted = extraction

    response = await cv_client.post("/settings/cv", data={"cv_tex": REAL_TEX})

    assert response.status_code == 200
    assert 'data-status="ok"' in response.text
    assert _BACKEND.calls[0]["schema"] is _ExtractedCv
    assert _BACKEND.calls[0]["text"] == REAL_TEX
    facts = load_facts(cv_dir / "cv.yaml")
    assert "Ghost Corp" not in {org.name for org in facts.orgs}
    assert "Invented Role" not in {title.name for title in facts.titles}
