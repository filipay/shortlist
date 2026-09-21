"""CV-04 / CV-06 / Pattern P5 — the render path is deterministic and escaped.

Three controls: a render-twice-identical test, an AST scan proving no clock,
randomness or uuid import (and no clock-attribute call) is reachable from the
render path, and the hostile-bullet escaping test. Every guard has a companion
proving it can fail.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from markupsafe import Markup

from app.cv.factstore import load_facts
from app.domain.cv import CvFacts, apply_patch
from app.latex.env import _latex_finalize, make_latex_env
from app.latex.render import TEMPLATES_DIR, render_plan_to_tex

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"

#: Modules the render path must never import (Pattern P5's enemy table).
FORBIDDEN_MODULES = frozenset({"datetime", "time", "random", "uuid"})
#: Attribute names that read a clock.
CLOCK_ATTRIBUTES = frozenset({"now", "utcnow", "today"})

SCANNED_RENDER_MODULES = (
    PROJECT_ROOT / "app" / "latex" / "render.py",
    PROJECT_ROOT / "app" / "latex" / "env.py",
)


def _forbidden_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names & FORBIDDEN_MODULES


def _clock_attribute_calls(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in CLOCK_ATTRIBUTES
    }


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
                            "bullets": [
                                {"id": "bul/acme-ltd-2021/1", "text": text}
                            ],
                        }
                    ],
                }
            ],
            "orgs": [{"id": "org.acme", "name": "Acme Ltd"}],
            "titles": [{"id": "title.engineer", "name": "Engineer"}],
            "gaps": [],
        }
    )


# --- determinism --------------------------------------------------------------


def test_rendering_the_same_plan_twice_is_byte_identical() -> None:
    plan = apply_patch(load_facts(FIXTURE))

    assert render_plan_to_tex(plan) == render_plan_to_tex(plan)


def test_no_clock_randomness_or_uuid_import_is_reachable_from_the_render_path() -> None:
    offenders: dict[str, list[str]] = {}
    scanned = 0

    for path in SCANNED_RENDER_MODULES:
        scanned += 1
        found = sorted(_forbidden_imports(path.read_text(encoding="utf-8")))
        if found:
            offenders[str(path.relative_to(PROJECT_ROOT))] = found

    assert scanned == len(SCANNED_RENDER_MODULES), "a render module was not scanned"
    assert offenders == {}, f"a non-determinism source is reachable: {offenders}"


def test_no_clock_attribute_is_called_from_the_render_path() -> None:
    offenders: dict[str, list[str]] = {}

    for path in SCANNED_RENDER_MODULES:
        found = sorted(_clock_attribute_calls(path.read_text(encoding="utf-8")))
        if found:
            offenders[str(path.relative_to(PROJECT_ROOT))] = found

    assert offenders == {}, f"a clock attribute is called: {offenders}"


def test_the_determinism_scan_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    assert _forbidden_imports("import datetime\nimport random\n") == {
        "datetime",
        "random",
    }
    assert _clock_attribute_calls("x = datetime.datetime.now()") == {"now"}


# --- escaping through a real render -------------------------------------------


def test_the_hostile_bullet_is_escaped_in_the_rendered_output() -> None:
    plan = apply_patch(_facts_with_bullet("R&D cut latency 20% on a C++ _p99_ job"))

    rendered = render_plan_to_tex(plan)

    assert r"R\&D" in rendered
    assert r"20\%" in rendered
    assert r"\_p99\_" in rendered
    assert "R&D" not in rendered
    assert "20%" not in rendered
    assert "_p99_" not in rendered


def test_markup_passes_through_unescaped_while_a_plain_string_is_escaped() -> None:
    env = make_latex_env(TEMPLATES_DIR)
    template = env.from_string(r"\VAR{value}")

    assert template.render(value="a & b") == r"a \& b"
    # The explicit opt-out is the ONLY way out (D-67).
    assert template.render(value=Markup("a & b")) == "a & b"


# --- the choke point itself ---------------------------------------------------


def test_the_environment_installs_finalize_and_registers_no_escaping_filter() -> None:
    env = make_latex_env(TEMPLATES_DIR)

    assert env.finalize is _latex_finalize
    assert env.autoescape is False
    assert [name for name in env.filters if "escape" in name] == []


def test_the_golden_and_template_paths_are_pinned_to_lf_endings() -> None:
    text = (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "tests/golden/**" in text
    assert "app/latex/templates/**" in text
    assert text.count("eol=lf") >= 2


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
