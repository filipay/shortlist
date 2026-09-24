"""TAIL-02 / D-103 / D-104 / D-105 / D-106 — the five-operation patch engine.

The engine is the spine of Phase 6: it turns a typed patch over enumerated fact ids
into a deterministic ``RenderPlan``. These cases pin the ordering semantics
(D-103/D-104), the all-or-nothing validation (D-106), the immutability of
``Bullet.text`` (TAIL-03) and the wire schema (``additionalProperties: false``).

The domain has no I/O, so the fact stores here are built in memory.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.cv import (
    BulletMove,
    BulletWeight,
    CvFacts,
    DemoteBullet,
    DropBullet,
    InvalidPatchError,
    ReorderSection,
    TailoringPatch,
    UnknownIdError,
    apply_patch,
    facts_hash,
    verify_original_matches,
)
from app.latex.render import render_plan_to_tex

ENTRY = "exp/acme-ltd-2021"
OTHER_ENTRY = "exp/acme-ltd-2020"


def _facts_dict() -> dict:
    return {
        "schema_version": 1,
        "meta": {
            "name": "Alex Example",
            "contact": {"email": "alex.example@example.invalid"},
            "max_pages": 2,
        },
        "sections": [
            {
                "id": "sec.experience",
                "title_key": "sec.experience",
                "order": 10,
                "entries": [
                    {
                        "id": ENTRY,
                        "org_id": "org.acme",
                        "title_id": "title.engineer",
                        "start": "2021-03",
                        "end": "2024-09",
                        "bullets": [
                            {"id": "bul/acme-ltd-2021/1", "text": "First"},
                            {"id": "bul/acme-ltd-2021/2", "text": "Second"},
                            {"id": "bul/acme-ltd-2021/3", "text": "Third"},
                        ],
                    },
                    {
                        "id": OTHER_ENTRY,
                        "org_id": "org.acme",
                        "title_id": "title.engineer",
                        "start": "2020-01",
                        "end": "2021-02",
                        "bullets": [{"id": "bul/acme-ltd-2020/1", "text": "Earlier"}],
                    },
                ],
            },
            {
                "id": "sec.skills",
                "title_key": "sec.skills",
                "order": 30,
                "entries": [],
                "skills": [
                    {"id": "skill.python", "label": "Python", "group": "languages"}
                ],
            },
        ],
        "orgs": [{"id": "org.acme", "name": "Acme Ltd"}],
        "titles": [{"id": "title.engineer", "name": "Engineer"}],
        "gaps": [],
    }


def _facts() -> CvFacts:
    return CvFacts.model_validate(_facts_dict())


def _patch(*ops) -> TailoringPatch:
    return TailoringPatch(listing_id=1, ops=list(ops))


def _texts(plan, entry_id: str) -> list[str]:
    for section in plan.sections:
        for entry in section.entries:
            if entry.id == entry_id:
                return [bullet.text for bullet in entry.bullets]
    raise AssertionError(f"entry {entry_id!r} not in plan")


# --- D-103: reweight means within-entry ordering -------------------------------


def test_reweight_reorders_within_the_entry_by_weight_descending() -> None:
    facts = _facts()
    patch = _patch(
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/3", weight=2.0)
    )

    # Bullets 1 and 2 are unreweighted (neutral 1.0); bullet 3 -> 2.0 goes first.
    assert _texts(apply_patch(facts, patch), ENTRY) == ["Third", "First", "Second"]


def test_reweight_ties_keep_declaration_order() -> None:
    facts = _facts()
    patch = _patch(
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/1", weight=2.0),
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/3", weight=2.0),
    )

    # 1 and 3 tie at 2.0: declaration order keeps 1 before 3; 2 stays last.
    assert _texts(apply_patch(facts, patch), ENTRY) == ["First", "Third", "Second"]


# --- D-104: demote is lowest prominence ----------------------------------------


def test_demote_lands_after_every_non_demoted_bullet() -> None:
    facts = _facts()
    patch = _patch(
        DemoteBullet(
            op="demote_bullet", bullet_id="bul/acme-ltd-2021/1", reason="less relevant"
        )
    )

    assert _texts(apply_patch(facts, patch), ENTRY) == ["Second", "Third", "First"]


def test_demoted_bullets_keep_declaration_order_among_themselves() -> None:
    facts = _facts()
    patch = _patch(
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/3", reason="r"),
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/1", reason="r"),
    )

    # Both demoted: they fall to the tail in DECLARATION order (1 then 3).
    assert _texts(apply_patch(facts, patch), ENTRY) == ["Second", "First", "Third"]


# --- move is the explicit positional override ---------------------------------


def test_move_with_no_destination_inserts_first() -> None:
    facts = _facts()
    patch = _patch(BulletMove(op="move_bullet", bullet_id="bul/acme-ltd-2021/3"))

    assert _texts(apply_patch(facts, patch), ENTRY) == ["Third", "First", "Second"]


def test_move_honours_an_explicit_destination() -> None:
    facts = _facts()
    patch = _patch(
        BulletMove(
            op="move_bullet",
            bullet_id="bul/acme-ltd-2021/1",
            before_id="bul/acme-ltd-2021/3",
        )
    )

    # Remove 1 -> [2, 3]; insert before 3 -> [2, 1, 3].
    assert _texts(apply_patch(facts, patch), ENTRY) == ["Second", "First", "Third"]


def test_move_wins_over_reweight_for_its_own_bullet() -> None:
    facts = _facts()
    patch = _patch(
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/1", weight=2.0),
        BulletMove(op="move_bullet", bullet_id="bul/acme-ltd-2021/3"),
    )

    # Base order by weight: 1 (2.0), 2 (1.0), 3 (1.0) -> [1, 2, 3]; then 3 moves first.
    assert _texts(apply_patch(facts, patch), ENTRY) == ["Third", "First", "Second"]


# --- drop removes and records the reason ---------------------------------------


def test_drop_removes_the_bullet_and_records_its_reason() -> None:
    facts = _facts()
    patch = _patch(
        DropBullet(
            op="drop_bullet",
            bullet_id="bul/acme-ltd-2021/2",
            reason="irrelevant to this role",
        )
    )

    plan = apply_patch(facts, patch)

    assert _texts(plan, ENTRY) == ["First", "Third"]
    (change,) = plan.changes
    assert change.op == "drop_bullet"
    assert change.target_id == "bul/acme-ltd-2021/2"
    assert change.detail == "irrelevant to this role"


def test_a_drop_or_demote_with_an_empty_reason_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        DropBullet(op="drop_bullet", bullet_id="bul/acme-ltd-2021/2", reason="")
    with pytest.raises(ValidationError):
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/2", reason="")


# --- section reorder -----------------------------------------------------------


def test_reorder_section_moves_the_section_and_records_the_new_order() -> None:
    facts = _facts()
    patch = _patch(ReorderSection(op="reorder_section", section_id="sec.skills", order=5))

    plan = apply_patch(facts, patch)

    assert [section.title for section in plan.sections] == ["Skills", "Experience"]
    (change,) = plan.changes
    assert change.op == "reorder_section"
    assert change.target_id == "sec.skills"
    assert change.detail == "5"


def test_a_reorder_section_on_a_non_section_id_raises() -> None:
    """WR-02: a section op must resolve its section_id against the SECTION-id set only."""
    facts = _facts()

    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(
                ReorderSection(
                    op="reorder_section", section_id="bul/acme-ltd-2021/1", order=5
                )
            ),
        )


def test_every_change_record_describes_an_effect_at_the_right_locus() -> None:
    """TAIL-08: every change-log entry names a real fact at its op family's own locus.

    Per-op-locus, NOT "every record changed the output": a valid-id no-op (a move
    before itself, a reweight to the current weight) legitimately still records. The
    property pinned here is that a record's target is a real source fact of that op
    family's kind — and, for a drop, one the built plan no longer carries.
    """
    facts = _facts()
    patch = _patch(
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/2", weight=2.0),
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/3", reason="r"),
        DropBullet(op="drop_bullet", bullet_id="bul/acme-ltd-2020/1", reason="r"),
        BulletMove(op="move_bullet", bullet_id="bul/acme-ltd-2021/1"),
        ReorderSection(op="reorder_section", section_id="sec.skills", order=5),
    )

    plan = apply_patch(facts, patch)

    source_bullet_ids = {
        bullet.id for entry in facts.all_entries() for bullet in entry.bullets
    }
    plan_bullet_ids = {
        bullet.id
        for section in plan.sections
        for entry in section.entries
        for bullet in entry.bullets
    }
    plan_section_ids = {section.id for section in plan.sections}

    # Each op produced its record (asserted by content, not by a structural count).
    assert {change.target_id for change in plan.changes} == {
        "bul/acme-ltd-2021/2",
        "bul/acme-ltd-2021/3",
        "bul/acme-ltd-2020/1",
        "bul/acme-ltd-2021/1",
        "sec.skills",
    }

    for change in plan.changes:
        if change.op == "drop_bullet":
            # A drop names a source bullet the built plan no longer carries — the
            # assertion a phantom drop (a non-source id) would violate.
            assert change.target_id in source_bullet_ids
            assert change.target_id not in plan_bullet_ids
        elif change.op in {"reweight_bullet", "demote_bullet", "move_bullet"}:
            assert change.target_id in plan_bullet_ids
        elif change.op == "reorder_section":
            assert change.target_id in plan_section_ids
        else:  # pragma: no cover
            raise AssertionError(f"unexpected op {change.op!r}")


# --- D-106: all-or-nothing validation ------------------------------------------


def test_an_unknown_id_raises_unknown_id_error() -> None:
    facts = _facts()

    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(
                BulletMove(
                    op="move_bullet",
                    bullet_id="bul/acme-ltd-2021/1",
                    before_id="bul/nope/1",
                )
            ),
        )
    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(BulletWeight(op="reweight_bullet", bullet_id="bul/nope/1", weight=1.0)),
        )


def test_a_bullet_op_on_a_non_bullet_fact_id_raises() -> None:
    """WR-02: a bullet op must resolve its bullet ids against the BULLET-id set only.

    A skill, section, entry, org, title or gap id used to satisfy the full fact-id
    grounding, no-op in ``_build_plan`` and still emit a ``ChangeRecord`` — a phantom
    change-log entry for a drop/reweight/demote/move that never happened.
    """
    facts = _facts()

    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(DropBullet(op="drop_bullet", bullet_id="skill.python", reason="r")),
        )
    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(BulletWeight(op="reweight_bullet", bullet_id="sec.skills", weight=1.5)),
        )
    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(DemoteBullet(op="demote_bullet", bullet_id="sec.experience", reason="r")),
        )
    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            _patch(
                BulletMove(
                    op="move_bullet",
                    bullet_id="bul/acme-ltd-2021/1",
                    before_id="skill.python",
                )
            ),
        )

    # Positive control: a real bullet id still validates and applies.
    plan = apply_patch(
        facts,
        _patch(DropBullet(op="drop_bullet", bullet_id="bul/acme-ltd-2021/1", reason="r")),
    )
    assert _texts(plan, ENTRY) == ["Second", "Third"]


def test_a_duplicate_target_raises_invalid_patch_error() -> None:
    facts = _facts()
    patch = _patch(
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/1", weight=1.5),
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/1", reason="r"),
    )

    with pytest.raises(InvalidPatchError):
        apply_patch(facts, patch)


def test_a_cross_entry_move_raises_invalid_patch_error() -> None:
    facts = _facts()
    patch = _patch(
        BulletMove(
            op="move_bullet",
            bullet_id="bul/acme-ltd-2021/1",
            before_id="bul/acme-ltd-2020/1",
        )
    )

    with pytest.raises(InvalidPatchError):
        apply_patch(facts, patch)


def test_an_unknown_gap_evidence_id_raises() -> None:
    from app.domain.cv import GapFinding

    facts = _facts()
    patch = TailoringPatch(
        listing_id=1,
        gaps=[GapFinding(requirement="Rust", status="direct", evidence_ids=["bul/nope/1"])],
    )

    with pytest.raises(UnknownIdError):
        apply_patch(facts, patch)


# --- identity + immutability ---------------------------------------------------


def test_apply_patch_without_a_patch_and_with_an_empty_patch_are_identical() -> None:
    facts = _facts()

    implicit = apply_patch(facts)
    explicit = apply_patch(facts, TailoringPatch(listing_id=1))

    assert implicit == explicit
    assert implicit.changes == []


def test_every_operation_preserves_bullet_text_byte_for_byte() -> None:
    facts = _facts()
    source = {b.id: b.text for entry in facts.all_entries() for b in entry.bullets}
    patch = _patch(
        BulletWeight(op="reweight_bullet", bullet_id="bul/acme-ltd-2021/1", weight=2.0),
        BulletMove(op="move_bullet", bullet_id="bul/acme-ltd-2021/3"),
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/2", reason="r"),
    )

    plan = apply_patch(facts, patch)

    seen = 0
    for section in plan.sections:
        for entry in section.entries:
            for bullet in entry.bullets:
                seen += 1
                assert bullet.text == source[bullet.id]
    assert seen == len(source)


def test_the_same_patch_renders_to_byte_identical_tex_twice() -> None:
    facts = _facts()
    patch = _patch(
        DemoteBullet(op="demote_bullet", bullet_id="bul/acme-ltd-2021/2", reason="r")
    )

    first = render_plan_to_tex(apply_patch(facts, patch))
    second = render_plan_to_tex(apply_patch(facts, patch))

    assert first == second


# --- the wire schema -----------------------------------------------------------


def test_the_patch_schema_forbids_extras_and_carries_no_free_text_render_field() -> None:
    schema = TailoringPatch.model_json_schema()
    op_names = ("BulletMove", "BulletWeight", "DemoteBullet", "DropBullet", "ReorderSection")

    for name in op_names:
        assert schema["$defs"][name]["additionalProperties"] is False, name
        properties = set(schema["$defs"][name]["properties"])
        assert properties <= {
            "op",
            "bullet_id",
            "before_id",
            "weight",
            "reason",
            "section_id",
            "order",
        }, (name, properties)


# --- the optimistic-concurrency guard ------------------------------------------


def test_facts_hash_changes_when_a_fact_changes() -> None:
    facts = _facts()
    mutated = facts.model_copy(deep=True)
    mutated.sections[0].entries[0].bullets[0].text = "Different"

    assert facts_hash(facts) != facts_hash(mutated)


def test_verify_original_matches_names_the_failed_check() -> None:
    facts = _facts()
    captured = facts_hash(facts)

    assert (
        verify_original_matches(
            facts, captured_hash=captured, captured_version_id=3, current_version_id=3
        ).ok
        is True
    )
    assert (
        verify_original_matches(
            facts, captured_hash="deadbeef", captured_version_id=3, current_version_id=3
        ).reason
        == "fact_store_changed"
    )
    assert (
        verify_original_matches(
            facts, captured_hash=captured, captured_version_id=3, current_version_id=4
        ).reason
        == "cv_version_changed"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
