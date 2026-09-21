"""CV-03 / CV-06 / D-68 / D-70 / D-72 — the fact-equivalence half of the golden pair.

Run it with:

    docker compose run --rm app pytest -m latex

Plan 04-03 shipped the byte-exact half in the hermetic lane. This is the second of
D-68's two tests with two failure classes: it extracts text from **two compiled
PDFs** — the human's `.tex` fixture and the `.tex` the renderer produces from the
fact store — and measures the artefact a human and an ATS actually read. The two
templates are different by design, so byte equality between them is neither
required nor possible; the only meaningful comparison reduces both sides to facts.

**Why membership and never a ratio.** The check is a strict membership test after
normalisation, with the whitespace-insensitive canonical form as the only
concession to the extractor's loss. A fuzzy similarity ratio was rejected: a high
ratio over a long section can hide exactly the dropped bullet CV-R5 exists to
catch, so a ratio would make the predicate pass on the failure it is built to
find.

**Why every predicate call carries a floor.** Asserting only "the compile
succeeded" is not a check — a compile can succeed on a document that lost every
bullet. Each comparison asserts a minimum fact count first, and an empty
extraction is shown to fail, so nothing here passes vacuously.

The engine lives only inside the image (D-69), so on a dry host these nodes are
COLLECTED and SKIPPED — never deselected — and the skip reason names the gate.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.cv.factstore import load_facts
from app.domain.cv import CvFacts, apply_patch
from app.domain.tex import facts_compared, facts_present_in
from app.latex.compile import TectonicEngine, extract_pdf_text
from app.latex.render import render_plan_to_tex

pytestmark = [
    pytest.mark.latex,
    pytest.mark.skipif(
        shutil.which(settings.tectonic_binary) is None,
        reason=(
            "the LaTeX engine lives only inside the image: "
            "docker compose run --rm app pytest -m latex"
        ),
    ),
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HUMAN_TEX = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.tex"
FACTS_YAML = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"

#: The floor on how many facts a comparison must cover. The fixture yields
#: ``3 + len(bullets)`` per entry: one entry with three bullets is exactly 6. A
#: run below this is a run that compared almost nothing and must not pass.
MIN_FACTS_COMPARED = 6
#: The floor below which an extraction is implausibly short for a CV PDF.
MIN_EXTRACTED_CHARS = 40
#: The one-line hostile bullet that exercises the ampersand, percent, underscore,
#: hash, dollar, tilde, caret and brace characters end to end (CV-06).
HOSTILE_BULLET = "R&D cut latency 20% on a C++ _p99_ job (#1, $5, ~, ^, {})"
MIN_HOSTILE_FACTS = 4


def _engine() -> TectonicEngine:
    return TectonicEngine(
        binary=settings.tectonic_binary,
        cache_dir=settings.tectonic_cache_dir,
        offline=True,
        timeout=settings.tectonic_timeout_seconds,
    )


def _compile_and_extract(tex: str, workdir: Path) -> tuple[str, object]:
    """Compile `tex`, then extract its text. A failed compile is a hard failure."""
    result = asyncio.run(_engine().compile(tex=tex, workdir=workdir))
    assert result.ok is True, result
    assert result.pdf_path is not None, result
    return extract_pdf_text(Path(result.pdf_path)), result


def _facts_with_bullet(text: str) -> CvFacts:
    """A minimal single-entry, single-bullet fact store around `text`."""
    return CvFacts.model_validate(
        {
            "schema_version": 1,
            "meta": {
                "name": "Test Person",
                "contact": {"email": "test@example.invalid"},
                "max_pages": 2,
            },
            "sections": [
                {
                    "id": "sec.experience",
                    "title_key": "sec.experience",
                    "order": 10,
                    "entries": [
                        {
                            "id": "exp/acme-ltd-2021",
                            "org_id": "org.acme",
                            "title_id": "title.engineer",
                            "start": "2021-03",
                            "end": "2024-09",
                            "location": "Dublin, IE",
                            "bullets": [{"id": "bul/acme-ltd-2021/1", "text": text}],
                        }
                    ],
                }
            ],
            "orgs": [{"id": "org.acme", "name": "Acme Ltd"}],
            "titles": [{"id": "title.engineer", "name": "Engineer"}],
            "gaps": [],
        }
    )


@pytest.fixture(scope="session")
def compiled_pair(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[CvFacts, str, str]:
    """Compile both sides once per session; the assertions stay cheap."""
    if shutil.which(settings.tectonic_binary) is None:
        pytest.skip(
            "the LaTeX engine lives only inside the image: "
            "docker compose run --rm app pytest -m latex"
        )

    facts = load_facts(FACTS_YAML)
    root = tmp_path_factory.mktemp("fact-equivalence")

    human_text, _ = _compile_and_extract(
        HUMAN_TEX.read_text(encoding="utf-8"), root / "human"
    )
    rendered_tex = render_plan_to_tex(apply_patch(facts))
    rendered_text, _ = _compile_and_extract(rendered_tex, root / "rendered")

    return facts, human_text, rendered_text


# --- the two compiles and their extractions -----------------------------------


def test_the_human_document_extracts_to_real_text(
    compiled_pair: tuple[CvFacts, str, str],
) -> None:
    _, human_text, _ = compiled_pair
    assert len(human_text) >= MIN_EXTRACTED_CHARS, repr(human_text)


def test_the_rendered_document_extracts_to_real_text(
    compiled_pair: tuple[CvFacts, str, str],
) -> None:
    _, _, rendered_text = compiled_pair
    assert len(rendered_text) >= MIN_EXTRACTED_CHARS, repr(rendered_text)


# --- fact equivalence, with the floor on every call ---------------------------


def test_the_rendered_pdf_carries_every_fact(
    compiled_pair: tuple[CvFacts, str, str],
) -> None:
    facts, _, rendered_text = compiled_pair
    compared = facts_compared(facts)
    assert compared >= MIN_FACTS_COMPARED, compared

    present, missing = facts_present_in(facts, rendered_text)
    assert present is True, missing
    assert missing == []


def test_the_human_pdf_carries_every_fact(
    compiled_pair: tuple[CvFacts, str, str],
) -> None:
    facts, human_text, _ = compiled_pair
    compared = facts_compared(facts)
    assert compared >= MIN_FACTS_COMPARED, compared

    present, missing = facts_present_in(facts, human_text)
    assert present is True, missing


def test_the_floor_is_load_bearing_so_an_empty_extraction_cannot_pass(
    compiled_pair: tuple[CvFacts, str, str],
) -> None:
    facts, _, _ = compiled_pair
    compared = facts_compared(facts)
    assert compared >= MIN_FACTS_COMPARED, compared

    present, missing = facts_present_in(facts, "")
    assert present is False
    assert missing


# --- D-72: the control that proves the predicate discriminates ----------------


def test_the_check_fails_on_a_mutated_fact_store(tmp_path: Path) -> None:
    """A guard that cannot fail is not a guard.

    The identical predicate, run over the SAME input class a bug would produce —
    one bullet's text changed and one date shifted — must now report inequality
    and name the mutated bullet.
    """
    facts = load_facts(FACTS_YAML)
    mutated = facts.model_copy(deep=True)
    entry = mutated.sections[0].entries[0]
    original_bullet = entry.bullets[0].text
    # A replacement that does NOT contain the original as a substring, so the
    # mutation cannot slip through a substring membership test.
    entry.bullets[0].text = "Rewrote the ingest path for a different team"
    entry.end = "2024-10"

    mutated_tex = render_plan_to_tex(apply_patch(mutated))
    mutated_text, _ = _compile_and_extract(mutated_tex, tmp_path)

    compared = facts_compared(facts)
    assert compared >= MIN_FACTS_COMPARED, compared

    present, missing = facts_present_in(facts, mutated_text)
    assert present is False
    assert original_bullet in missing


# --- CV-06 end to end: escaping survives the engine, not just the string pass --


def test_a_hostile_bullet_survives_the_engine_and_extraction(tmp_path: Path) -> None:
    facts = _facts_with_bullet(HOSTILE_BULLET)

    hostile_tex = render_plan_to_tex(apply_patch(facts))
    hostile_text, _ = _compile_and_extract(hostile_tex, tmp_path)

    assert hostile_text.strip(), repr(hostile_text)

    compared = facts_compared(facts)
    assert compared >= MIN_HOSTILE_FACTS, compared

    present, missing = facts_present_in(facts, hostile_text)
    assert present is True, missing


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
