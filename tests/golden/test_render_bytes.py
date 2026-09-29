"""D-68 / D-72 — the byte-exact half of the golden reproduction.

This is the first of D-68's two tests with two failure classes. It senses
renderer determinism and template regressions and needs **no engine**, so it runs
in the hermetic default lane. Its counterpart — fact-equivalence over the text
extracted from two compiled PDFs — is plan 04-04's.

The split is not cosmetic: ``render(cv.yaml)`` and the human's own document are
different templates by design, so byte equality between them is neither required
nor possible; the only meaningful comparison between those two artefacts reduces
both sides to extracted facts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cv.factstore import load_facts
from app.domain.cv import apply_patch
from app.latex.render import render_plan_to_tex

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"
#: The committed baseline. It is generated once from a REVIEWED render and then
#: committed; this test never writes it, because a golden test that writes its own
#: expectation grades its own homework.
GOLDEN = Path(__file__).resolve().parent / "base.rendered.tex"


def _render_fixture_bytes() -> bytes:
    facts = load_facts(FIXTURE)
    return render_plan_to_tex(apply_patch(facts)).encode("utf-8")


def test_a_meta_location_renders_in_the_header_and_the_baseline_is_unchanged() -> None:
    """A location-less store keeps the golden; a set location reaches the header."""
    facts = load_facts(FIXTURE)
    assert facts.meta.location is None

    # No location -> byte-identical to the committed golden baseline.
    assert _render_fixture_bytes() == GOLDEN.read_bytes()

    located = facts.model_copy(
        update={
            "meta": facts.meta.model_copy(
                update={"location": "Exampleville, Exampleland"}
            )
        }
    )
    rendered = render_plan_to_tex(apply_patch(located))

    assert "Exampleville, Exampleland" in rendered
    header = rendered.split("\\end{center}", 1)[0]
    assert "Exampleville, Exampleland" in header
    # The header changed, so the baseline is provably sensitive to the new field.
    assert rendered != GOLDEN.read_text(encoding="utf-8")


def test_the_rendered_tex_matches_the_committed_golden_baseline() -> None:
    # A BYTES read, not a text read: an encoding or line-ending difference is
    # exactly the class of regression this exists to catch.
    assert _render_fixture_bytes() == GOLDEN.read_bytes()


def test_the_byte_comparison_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    baseline = bytearray(GOLDEN.read_bytes())
    # Mutate one character of the committed baseline in memory.
    marker = b"Alex Example"
    index = bytes(baseline).index(marker)
    baseline[index] = ord("B")

    assert _render_fixture_bytes() != bytes(baseline)


def test_the_golden_file_is_never_written_by_the_test() -> None:
    """The test reads the golden and nothing else."""
    before = GOLDEN.stat().st_mtime_ns

    _render_fixture_bytes()

    assert GOLDEN.stat().st_mtime_ns == before


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
