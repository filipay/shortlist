"""PITFALLS P13 — the Layer-1 fixture builder.

No LLM, no compiler, no network and no clock: facts load from the committed
stand-in fact store, a plan comes from ``apply_patch(facts, patch)``, and the
extracted ``text`` is read from a committed ``tests/fixtures/verify/*.txt`` (a
hand-written pypdf-style extraction). The temporal ``now`` is INJECTED by the
caller, so the default lane stays clock-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cv.factstore import load_facts
from app.domain.cv import CvFacts, RenderPlan, TailoringPatch, apply_patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FACTS_YAML = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"
VERIFY_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "verify"


@dataclass(frozen=True)
class VerifyFixture:
    """One Layer-1 case: the inputs, the extraction, and whether it should pass."""

    facts: CvFacts
    plan: RenderPlan
    patch: TailoringPatch
    text: str
    page_count: int
    expected: bool


def load_standin_facts() -> CvFacts:
    return load_facts(FACTS_YAML)


def build_fixture(
    patch: TailoringPatch | None = None,
    *,
    extract_name: str = "base_extract.txt",
    page_count: int = 1,
    expected: bool = True,
) -> VerifyFixture:
    facts = load_standin_facts()
    resolved = patch or TailoringPatch(listing_id=1)
    plan = apply_patch(facts, resolved)
    text = (VERIFY_FIXTURES / extract_name).read_text(encoding="utf-8")
    return VerifyFixture(
        facts=facts,
        plan=plan,
        patch=resolved,
        text=text,
        page_count=page_count,
        expected=expected,
    )


__all__ = ["FACTS_YAML", "VERIFY_FIXTURES", "VerifyFixture", "build_fixture", "load_standin_facts"]
