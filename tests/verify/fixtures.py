"""PITFALLS P13 — the Layer-1 fixture builder.

No LLM, no compiler, no network and no clock: facts load from the committed
stand-in fact store, a plan comes from ``apply_patch(facts, patch)``, and the
extracted ``text`` is read from a committed ``tests/fixtures/verify/*.txt`` (a
hand-written pypdf-style extraction). The temporal ``now`` is INJECTED by the
caller, so the default lane stays clock-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    #: Per-requirement grounding expectations (A1's advisory band): requirement text
    #: -> the band the fixture expects. Empty unless the case exercises check 6.
    bands: dict[str, str] = field(default_factory=dict)


def load_standin_facts() -> CvFacts:
    return load_facts(FACTS_YAML)


def with_digit_skill(
    facts: CvFacts, *, label: str = "AWS S3", group: str = "infrastructure"
) -> CvFacts:
    """A copy of ``facts`` whose LAST skill of every skill-bearing section carries ``label``.

    Rebuilt through ``model_copy`` so the loaded stand-in object is never mutated and
    ``tests/golden/base.rendered.tex`` cannot shift. A section with no skills is
    returned unchanged. The digit ``3`` in the default label is ordinary CV content
    (the verifier's own example), not a fabricated metric.
    """
    sections = []
    for section in facts.sections:
        if not section.skills:
            sections.append(section)
            continue
        skills = list(section.skills)
        skills[-1] = skills[-1].model_copy(update={"label": label, "group": group})
        sections.append(section.model_copy(update={"skills": skills}))
    return facts.model_copy(update={"sections": sections})


def with_digit_location(
    facts: CvFacts, *, location: str = "Dublin 2"
) -> CvFacts:
    """A copy of ``facts`` whose LAST entry of every entry-bearing section carries ``location``.

    Rebuilt through ``model_copy`` so the loaded stand-in is never mutated and
    ``tests/golden/base.rendered.tex`` cannot shift. A section with no entries is
    returned unchanged. The digit ``2`` in the default location is ordinary CV
    content (the verifier's own CR-01 example), not a fabricated metric.
    """
    sections = []
    for section in facts.sections:
        if not section.entries:
            sections.append(section)
            continue
        entries = list(section.entries)
        entries[-1] = entries[-1].model_copy(update={"location": location})
        sections.append(section.model_copy(update={"entries": entries}))
    return facts.model_copy(update={"sections": sections})


def build_fixture(
    patch: TailoringPatch | None = None,
    *,
    extract_name: str = "base_extract.txt",
    page_count: int = 1,
    expected: bool = True,
    bands: dict[str, str] | None = None,
    facts: CvFacts | None = None,
) -> VerifyFixture:
    resolved_facts = facts if facts is not None else load_standin_facts()
    resolved = patch or TailoringPatch(listing_id=1)
    plan = apply_patch(resolved_facts, resolved)
    text = (VERIFY_FIXTURES / extract_name).read_text(encoding="utf-8")
    return VerifyFixture(
        facts=resolved_facts,
        plan=plan,
        patch=resolved,
        text=text,
        page_count=page_count,
        expected=expected,
        bands=dict(bands) if bands else {},
    )


__all__ = [
    "FACTS_YAML",
    "VERIFY_FIXTURES",
    "VerifyFixture",
    "build_fixture",
    "load_standin_facts",
    "with_digit_location",
    "with_digit_skill",
]
