"""260929-pan — the pure page-budget trim selector.

``next_page_trim`` is a pure function over the plan's OWN carried order: the last
bullet of the last entry-bearing section is the document's lowest-value survivor.
These cases pin the bottom-first choice, the reason text, and the two eligibility
rules (an already-targeted bullet, and an entry's sole survivor) with in-memory
fact stores, mirroring ``tests/domain/test_patch_ops.py`` (no I/O, no clock).
"""

from __future__ import annotations

from app.domain.cv import (
    PAGE_TRIM_REASON_TEMPLATE,
    BulletMove,
    BulletWeight,
    CvFacts,
    DemoteBullet,
    DropBullet,
    TailoringPatch,
    apply_patch,
    iter_fact_ids,
    next_page_trim,
)
from tests.verify.fixtures import load_standin_facts

EXPERIENCE = "sec.experience"
PROJECTS = "sec.projects"
ENTRY = "exp/acme-ltd-2021"
OLDER = "exp/acme-ltd-2020"
SIDE = "exp/side-project-2022"

BULLET3 = "bul/acme-ltd-2021/3"
SIDE1 = "bul/side-project-2022/1"
SIDE2 = "bul/side-project-2022/2"


def _facts_dict(*, single_survivors: bool = False) -> dict:
    """Two ordered sections; the bottom of the document is the projects tail."""
    return {
        "schema_version": 1,
        "meta": {"name": "Alex Example", "max_pages": 2},
        "sections": [
            {
                "id": EXPERIENCE,
                "title_key": EXPERIENCE,
                "order": 10,
                "entries": [
                    {
                        "id": ENTRY,
                        "org_id": "org.acme",
                        "title_id": "title.engineer",
                        "start": "2021-03",
                        "end": "2024-09",
                        "bullets": [
                            {"id": f"bul/acme-ltd-2021/{i}", "text": f"B{i}"} for i in (1, 2, 3)
                        ],
                    },
                    {
                        "id": OLDER,
                        "org_id": "org.acme",
                        "title_id": "title.engineer",
                        "start": "2020-01",
                        "end": "2021-02",
                        "bullets": [{"id": "bul/acme-ltd-2020/1", "text": "Older"}],
                    },
                ],
            },
            {
                "id": PROJECTS,
                "title_key": PROJECTS,
                "order": 20,
                "entries": [
                    {
                        "id": SIDE,
                        "org_id": "org.acme",
                        "title_id": "title.engineer",
                        "start": "2022-01",
                        "end": "2022-12",
                        "bullets": [
                            {"id": SIDE1, "text": "Side one"},
                            {"id": SIDE2, "text": "Side two"},
                        ],
                    }
                ],
            },
        ],
        "orgs": [{"id": "org.acme", "name": "Acme Ltd"}],
        "titles": [{"id": "title.engineer", "name": "Engineer"}],
        "gaps": [],
    }


def _facts(*, single_survivors: bool = False) -> CvFacts:
    if single_survivors:
        data = _facts_dict()
        for section in data["sections"]:
            for entry in section["entries"]:
                entry["bullets"] = entry["bullets"][:1]
        return CvFacts.model_validate(data)
    return CvFacts.model_validate(_facts_dict())


def _patch(*ops) -> TailoringPatch:
    return TailoringPatch(listing_id=1, ops=list(ops))


# --- the bottom of the document wins -------------------------------------------


def test_it_chooses_the_bottom_of_the_document_first() -> None:
    facts = _facts()
    plan = apply_patch(facts)

    drop = next_page_trim(plan, TailoringPatch(listing_id=1), max_pages=2)

    assert drop is not None
    assert drop.bullet_id == SIDE2, "the last bullet of the last entry-bearing section"


def test_the_returned_id_is_a_real_fact_id_and_the_reason_names_the_budget() -> None:
    facts = _facts()
    drop = next_page_trim(apply_patch(facts), TailoringPatch(listing_id=1), max_pages=2)

    assert drop is not None
    assert drop.op == "drop_bullet"
    assert drop.bullet_id in set(iter_fact_ids(facts))
    assert drop.reason == PAGE_TRIM_REASON_TEMPLATE.format(limit=2)
    assert drop.reason, "a drop reason is required and non-empty"


def test_the_standin_facts_trim_their_last_bullet() -> None:
    facts = load_standin_facts()
    drop = next_page_trim(apply_patch(facts), TailoringPatch(listing_id=1), max_pages=2)

    assert drop is not None
    assert drop.bullet_id == "bul/northwind-labs-2021/3"
    assert drop.reason == PAGE_TRIM_REASON_TEMPLATE.format(limit=2)


# --- an already-targeted bullet is never returned -------------------------------


def test_a_reweighted_bullet_is_skipped() -> None:
    facts = _facts()
    patch = _patch(BulletWeight(op="reweight_bullet", bullet_id=SIDE2, weight=2.0))

    drop = next_page_trim(apply_patch(facts, patch), patch, max_pages=2)

    assert drop is not None
    assert drop.bullet_id == SIDE1, "the reweight target must not be trimmed"


def test_a_demoted_bullet_is_skipped() -> None:
    facts = _facts()
    patch = _patch(DemoteBullet(op="demote_bullet", bullet_id=SIDE2, reason="secondary"))

    drop = next_page_trim(apply_patch(facts, patch), patch, max_pages=2)

    assert drop is not None
    assert drop.bullet_id == SIDE1


def test_a_moved_bullet_is_skipped() -> None:
    facts = _facts()
    patch = _patch(BulletMove(op="move_bullet", bullet_id=SIDE2))

    drop = next_page_trim(apply_patch(facts, patch), patch, max_pages=2)

    assert drop is not None
    assert drop.bullet_id == SIDE1


def test_a_dropped_bullets_whole_entry_is_skipped_not_orphaned() -> None:
    facts = _facts()
    patch = _patch(DropBullet(op="drop_bullet", bullet_id=SIDE2, reason="gone"))

    drop = next_page_trim(apply_patch(facts, patch), patch, max_pages=2)

    assert drop is not None
    # The projects entry is now a sole survivor, so the walk falls back to the
    # experience tail rather than leaving the entry header with nothing under it.
    assert drop.bullet_id == BULLET3


# --- exhaustion -----------------------------------------------------------------


def test_it_returns_none_when_every_entry_has_a_single_survivor() -> None:
    facts = _facts(single_survivors=True)

    drop = next_page_trim(apply_patch(facts), TailoringPatch(listing_id=1), max_pages=2)

    assert drop is None


# --- the selector is pure and never rebuilds text -------------------------------


def test_it_does_not_mutate_the_plan_or_the_patch() -> None:
    facts = _facts()
    plan = apply_patch(facts)
    patch = _patch(DropBullet(op="drop_bullet", bullet_id=SIDE1, reason="r"))
    patch_before = patch.model_dump(mode="json")
    plan_before = _shape(plan)

    next_page_trim(plan, patch, max_pages=2)

    assert patch.model_dump(mode="json") == patch_before
    assert _shape(plan) == plan_before


def test_a_trim_keeps_the_entry_header_and_never_rebuilds_bullet_text() -> None:
    facts = _facts()
    patch = _patch(DropBullet(op="drop_bullet", bullet_id=SIDE2, reason="trimmed"))
    source = {bullet.id: bullet.text for entry in facts.all_entries() for bullet in entry.bullets}

    plan = apply_patch(facts, patch)
    entry = next(item for section in plan.sections for item in section.entries if item.id == SIDE)

    assert entry.org
    assert entry.title
    assert entry.dates
    assert [bullet.id for bullet in entry.bullets] == [SIDE1]
    for bullet in entry.bullets:
        assert bullet.text == source[bullet.id]


def _shape(plan) -> list:
    return [
        (
            section.id,
            [(entry.id, [bullet.id for bullet in entry.bullets]) for entry in section.entries],
        )
        for section in plan.sections
    ]


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
