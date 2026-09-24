"""TAIL-02 / TAIL-03 / ARCHITECTURE §7.3 L713 — no patch field becomes PDF text.

The load-bearing guarantee: *"There is no field anywhere in this schema that becomes
text in the PDF."* The patch's audit strings (a drop/demote ``reason``, a
``GapFinding.requirement``, a ``Suggestion.rationale``) are UI/audit-only. A canary
planted in every one of them must not appear in the rendered ``.tex`` (or anywhere a
renderer can reach on the plan), while the change log still carries the reason — the
audit trail keeps the text, only the render path drops it.

The comparison uses the normalising ``squash`` form, so a canary that differed from
its source only by ligature expansion or whitespace would still be caught (TAIL-03).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.domain.cv import (
    CvFacts,
    DemoteBullet,
    DropBullet,
    GapFinding,
    RenderPlan,
    Suggestion,
    TailoringPatch,
    apply_patch,
)
from app.domain.tex import squash
from app.latex.render import render_plan_to_tex
from tests.verify.fixtures import load_standin_facts

#: Distinctive, lowercase canaries. Defined HERE and never repeated in prose.
DROP_CANARY = "zqxjkv drop label"
DEMOTE_CANARY = "zqxjkv demote label"
REQUIREMENT_CANARY = "zqxjkv requirement label"
RATIONALE_CANARY = "zqxjkv rationale label"

CANARIES = (DROP_CANARY, DEMOTE_CANARY, REQUIREMENT_CANARY, RATIONALE_CANARY)

BULLET2 = "bul/northwind-labs-2021/2"
BULLET3 = "bul/northwind-labs-2021/3"


def _canary_patch() -> TailoringPatch:
    return TailoringPatch(
        listing_id=1,
        ops=[
            DropBullet(op="drop_bullet", bullet_id=BULLET2, reason=DROP_CANARY),
            DemoteBullet(op="demote_bullet", bullet_id=BULLET3, reason=DEMOTE_CANARY),
        ],
        gaps=[GapFinding(requirement=REQUIREMENT_CANARY, status="gap")],
        suggestions=[Suggestion(bullet_id=BULLET2, evidence_ids=[], rationale=RATIONALE_CANARY)],
    )


def _facts_and_plan() -> tuple[CvFacts, RenderPlan, TailoringPatch]:
    facts = load_standin_facts()
    patch = _canary_patch()
    return facts, apply_patch(facts, patch), patch


def _strings(value: Any) -> Iterator[str]:
    """Every string reachable in a nested JSON-like value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def test_a_reason_canary_never_reaches_the_rendered_tex() -> None:
    _, plan, _ = _facts_and_plan()

    tex = squash(render_plan_to_tex(plan))

    for canary in CANARIES:
        assert squash(canary) not in tex, f"a canary reached the .tex: {canary!r}"


def test_no_render_plan_field_reaches_a_canary() -> None:
    _, plan, _ = _facts_and_plan()

    render_strings = list(_strings([section.model_dump(mode="json") for section in plan.sections]))
    render_strings += [plan.name or "", plan.contact_email or "", *plan.contact_links]
    squashed = squash(" ".join(render_strings))

    for canary in CANARIES:
        assert squash(canary) not in squashed


def test_the_change_log_still_carries_the_reasons() -> None:
    """The audit trail keeps what the render path drops."""
    _, plan, patch = _facts_and_plan()

    details = squash(" ".join(change.detail for change in plan.changes))
    assert squash(DROP_CANARY) in details
    assert squash(DEMOTE_CANARY) in details

    patch_json = squash(patch.model_dump_json())
    for canary in CANARIES:
        assert squash(canary) in patch_json, "the patch's own JSON must carry the canary"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
