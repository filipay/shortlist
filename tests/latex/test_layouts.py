"""260930-lay — the three committed CV layouts render the same facts.

A layout is presentation only. Every layout must render the identical RenderPlan to
LaTeX, escaped through the same choke point, deterministically and with LF endings;
Classic must stay byte-identical to its committed golden, and an unset/unknown layout
must resolve to Classic. Modern and Compact gain their own committed goldens so a
future template edit cannot drift silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cv.factstore import load_facts
from app.domain.cv import CvFacts, apply_patch
from app.domain.tex import escape_tex
from app.latex.render import DEFAULT_LAYOUT, LAYOUTS, render_plan_to_tex

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
CLASSIC_GOLDEN = GOLDEN_DIR / "base.rendered.tex"
NEW_GOLDENS = {
    "modern": GOLDEN_DIR / "base.rendered.modern.tex",
    "compact": GOLDEN_DIR / "base.rendered.compact.tex",
}

#: Facts the stand-in store states; every layout must carry all of them.
EXPECTED_FACTS = (
    "Alex Example",
    "Experience",
    "Northwind Labs",
    "Senior Engineer",
    "Reduced p99 latency 40% by rewriting the ingest path",
    "Led the migration to a single-writer queue",
    "Mentored four engineers through their first on-call rotation",
    "Skills",
    "Python",
    "PostgreSQL",
    "Terraform",
)


def _plan():
    return apply_patch(load_facts(FIXTURE))


def _facts_with_bullet(text: str) -> CvFacts:
    return CvFacts.model_validate(
        {
            "schema_version": 1,
            "meta": {"name": "Test Person", "max_pages": 2},
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


# --- every layout renders ------------------------------------------------------


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_each_layout_renders_and_is_byte_identical_twice(layout: str) -> None:
    plan = _plan()

    first = render_plan_to_tex(plan, layout=layout)
    second = render_plan_to_tex(plan, layout=layout)

    assert first
    assert first == second


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_every_layout_carries_every_expected_fact(layout: str) -> None:
    rendered = render_plan_to_tex(_plan(), layout=layout)

    for fact in EXPECTED_FACTS:
        assert escape_tex(fact) in rendered, (layout, fact)


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_every_layout_escapes_a_hostile_bullet(layout: str) -> None:
    plan = apply_patch(_facts_with_bullet("R&D cut latency 20% on a C++ _p99_ job"))

    rendered = render_plan_to_tex(plan, layout=layout)

    assert r"R\&D" in rendered
    assert r"20\%" in rendered
    assert r"\_p99\_" in rendered
    assert "R&D" not in rendered
    assert "20%" not in rendered
    assert "_p99_" not in rendered


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_every_layout_output_is_lf_only(layout: str) -> None:
    encoded = render_plan_to_tex(_plan(), layout=layout).encode("utf-8")

    assert b"\r" not in encoded, "a CR would break the byte-exact goldens"


# --- the default can never move -------------------------------------------------


def test_render_without_a_layout_equals_classic_bytes() -> None:
    plan = _plan()

    assert render_plan_to_tex(plan) == render_plan_to_tex(plan, layout=DEFAULT_LAYOUT)
    assert render_plan_to_tex(plan).encode("utf-8") == CLASSIC_GOLDEN.read_bytes()


@pytest.mark.parametrize("layout", ["unknown", "", None, 7])
def test_an_unset_or_unknown_layout_equals_classic_bytes(layout) -> None:
    plan = _plan()

    assert render_plan_to_tex(plan, layout=layout) == render_plan_to_tex(
        plan, layout=DEFAULT_LAYOUT
    )


# --- the per-layout goldens -----------------------------------------------------


@pytest.mark.parametrize("layout", sorted(NEW_GOLDENS))
def test_the_new_layout_golden_is_pinned(layout: str) -> None:
    golden = NEW_GOLDENS[layout]

    assert render_plan_to_tex(_plan(), layout=layout).encode("utf-8") == golden.read_bytes()


@pytest.mark.parametrize("layout", sorted(NEW_GOLDENS))
def test_the_per_layout_comparison_can_actually_fail(layout: str) -> None:
    """A guard that cannot fail is not a guard."""
    baseline = bytearray(NEW_GOLDENS[layout].read_bytes())
    marker = b"Alex Example"
    index = bytes(baseline).index(marker)
    baseline[index] = ord("B")

    assert render_plan_to_tex(_plan(), layout=layout).encode("utf-8") != bytes(baseline)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
