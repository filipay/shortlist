"""POST /settings/cv converts a submitted LaTeX CV into the live fact store.

The route is a plain urlencoded POST (no python-multipart). Everything here is
asserted on observable behavior: files on disk and the rendered response, never a
private helper.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import settings
from app.cv.factstore import load_facts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALID_TEX = (PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.tex").read_text(
    encoding="utf-8"
)

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
