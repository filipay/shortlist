"""D-63/D-64/D-65 — stable IDs, the model family, and the identity-only patch.

The domain has no I/O, so every case here builds a ``CvFacts`` in memory.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.cv import (
    SECTION_TITLES,
    BulletWeight,
    CvFacts,
    DropBullet,
    Section,
    Suggestion,
    TailoringPatch,
    UnknownIdError,
    apply_patch,
    derive_bullet_id,
    derive_entry_id,
    qualify_entry_ids,
    slugify,
)
from app.latex.render import render_plan_to_tex


def _entry_dict(*, entry_id: str = "exp/northwind-labs-2021") -> dict:
    return {
        "id": entry_id,
        "org_id": "org.northwind",
        "title_id": "title.senior_engineer",
        "start": "2021-03",
        "end": "2024-09",
        "location": "Dublin, IE",
        "bullets": [
            {"id": "bul/northwind-labs-2021/1", "text": "Led the migration"},
            {"id": "bul/northwind-labs-2021/2", "text": "Mentored four engineers"},
        ],
    }


def _facts_dict(**overrides) -> dict:
    data = {
        "schema_version": 1,
        "meta": {
            "name": "Alex Example",
            "contact": {"email": "alex.example@example.invalid", "phone": None},
            "max_pages": 2,
        },
        "sections": [
            {
                "id": "sec.experience",
                "title_key": "sec.experience",
                "order": 10,
                "entries": [_entry_dict()],
            },
            {
                "id": "sec.skills",
                "title_key": "sec.skills",
                "order": 30,
                "skills": [
                    {"id": "skill.python", "label": "Python", "group": "languages"}
                ],
            },
        ],
        "orgs": [{"id": "org.northwind", "name": "Northwind Labs"}],
        "titles": [{"id": "title.senior_engineer", "name": "Senior Engineer"}],
        "gaps": [],
    }
    data.update(overrides)
    return data


def _facts() -> CvFacts:
    return CvFacts.model_validate(_facts_dict())


# --- Test 11: deterministic derivation ----------------------------------------


def test_derive_entry_id_uses_only_the_org_slug_and_start_year() -> None:
    assert derive_entry_id("Acme Ltd", "2021-03") == "exp/acme-ltd-2021"
    # A different month of the same year is the same identity.
    assert derive_entry_id("Acme Ltd", "2021-11") == "exp/acme-ltd-2021"
    # A different year is a different identity.
    assert derive_entry_id("Acme Ltd", "2022-03") == "exp/acme-ltd-2022"


def test_derive_bullet_id_is_positional_within_the_entry_slug() -> None:
    assert derive_bullet_id("exp/acme-ltd-2021", 3) == "bul/acme-ltd-2021/3"


def test_slugify_is_diacritic_insensitive_and_locale_free() -> None:
    assert slugify("Café Ltd") == "cafe-ltd"
    assert slugify("Northwind Labs") == "northwind-labs"


# --- Test 12: the collision rule ----------------------------------------------


def test_qualify_entry_ids_is_deterministic_and_records_collisions() -> None:
    pairs = [("Acme Ltd", "2021-03"), ("Acme Ltd", "2021-05"), ("Acme Ltd", "2021-09")]

    first = qualify_entry_ids(pairs)
    second = qualify_entry_ids(pairs)

    assert first == second == [
        "exp/acme-ltd-2021",
        "exp/acme-ltd-2021-2",
        "exp/acme-ltd-2021-3",
    ]


# --- Test 13: the D-64 claim — an edit retires the old ID ---------------------


def test_editing_a_bullet_text_retires_the_old_id_and_introduces_a_new_one() -> None:
    """D-64: an ID is assigned once and never reassigned.

    A content edit cannot reuse the old ID (the store is frozen and the renderer
    never renumbers, D-63), so the edited wording is represented as a NEW bullet
    appended after the existing ones: the two ID sets differ and the retired ID is
    absent from the new set.
    """
    entry_id = "exp/northwind-labs-2021"
    before = [derive_bullet_id(entry_id, index) for index in (1, 2, 3)]

    # The edit: bullet 3's wording changes -> it is retired and re-added at the
    # next free index. Nothing is renumbered.
    after = [before[0], before[1], derive_bullet_id(entry_id, 4)]

    assert set(before) - set(after) == {"bul/northwind-labs-2021/3"}
    assert set(after) - set(before) == {"bul/northwind-labs-2021/4"}
    assert before[2] not in after
    # The entry identity is untouched by a bullet-text edit.
    assert derive_entry_id("Northwind Labs", "2021-03") == entry_id


# --- Test 14: loud model failures ---------------------------------------------


def test_duplicate_ids_are_rejected() -> None:
    duplicate = _entry_dict(entry_id="exp/northwind-labs-2021")
    data = _facts_dict()
    data["sections"][0]["entries"] = [duplicate, _entry_dict()]

    with pytest.raises(ValidationError) as excinfo:
        CvFacts.model_validate(data)

    assert "duplicate" in str(excinfo.value).lower()


def test_a_missing_required_field_is_rejected() -> None:
    entry = _entry_dict()
    del entry["start"]
    data = _facts_dict()
    data["sections"][0]["entries"] = [entry]

    with pytest.raises(ValidationError) as excinfo:
        CvFacts.model_validate(data)

    assert "start" in str(excinfo.value)


def test_an_unknown_key_is_rejected() -> None:
    data = _facts_dict()
    data["meta"]["bogus_key"] = "surprise"

    with pytest.raises(ValidationError) as excinfo:
        CvFacts.model_validate(data)

    assert "bogus_key" in str(excinfo.value)


def test_an_unknown_section_title_key_is_rejected_naming_the_key() -> None:
    data = _facts_dict()
    data["sections"][1]["title_key"] = "sec.unmapped"

    with pytest.raises(ValidationError) as excinfo:
        CvFacts.model_validate(data)

    assert "sec.unmapped" in str(excinfo.value)


# --- Test 15: apply_patch is identity for no ops, real for the five ops -------


def test_apply_patch_with_no_operations_is_an_exact_identity() -> None:
    facts = _facts()

    plan = apply_patch(facts)

    assert [section.title for section in plan.sections] == ["Experience", "Skills"]
    assert plan.sections[0].entries[0].org == "Northwind Labs"
    assert plan.sections[0].entries[0].title == "Senior Engineer"
    assert plan.sections[0].entries[0].dates == "2021-03 -- 2024-09"
    assert [bullet.text for bullet in plan.sections[0].entries[0].bullets] == [
        "Led the migration",
        "Mentored four engineers",
    ]
    assert plan.sections[1].skills[0].label == "Python"
    assert plan.changes == []


def test_an_empty_patch_is_the_identity_plan_with_no_changes() -> None:
    facts = _facts()

    plan = apply_patch(facts, TailoringPatch(listing_id=7))

    assert plan == apply_patch(facts)
    assert plan.changes == []


def test_real_mutating_operations_are_applied_rather_than_refused() -> None:
    """The stub's UnsupportedPatchOp is gone: the five ops are implemented."""
    facts = _facts()
    patch = TailoringPatch(
        listing_id=1,
        ops=[
            BulletWeight(
                op="reweight_bullet", bullet_id="bul/northwind-labs-2021/1", weight=0.5
            ),
            DropBullet(
                op="drop_bullet",
                bullet_id="bul/northwind-labs-2021/2",
                reason="irrelevant",
            ),
        ],
    )

    plan = apply_patch(facts, patch)

    assert [bullet.text for bullet in plan.sections[0].entries[0].bullets] == [
        "Led the migration"
    ]
    assert [change.op for change in plan.changes] == ["reweight_bullet", "drop_bullet"]


def test_a_suggestion_is_validated_but_never_applied() -> None:
    """A Suggestion rides in the patch but is kept off the road to the PDF."""
    facts = _facts()
    patch = TailoringPatch(
        listing_id=1,
        suggestions=[
            Suggestion(bullet_id="bul/northwind-labs-2021/1", rationale="try this")
        ],
    )

    assert apply_patch(facts, patch) == apply_patch(facts)


def test_an_operation_referencing_an_unknown_id_raises() -> None:
    facts = _facts()

    with pytest.raises(UnknownIdError):
        apply_patch(
            facts,
            TailoringPatch(
                listing_id=1,
                ops=[
                    BulletWeight(
                        op="reweight_bullet",
                        bullet_id="bul/does-not-exist/1",
                        weight=1.0,
                    )
                ],
            ),
        )


# --- Test 16: the entries|skills alternation ----------------------------------


def test_a_section_may_carry_entries_only_skills_only_or_both() -> None:
    entries_only = _facts_dict()
    entries_only["sections"][1].pop("skills")
    assert CvFacts.model_validate(entries_only).sections[1].entries == []

    skills_only = _facts_dict()
    skills_only["sections"][0].pop("entries")
    assert CvFacts.model_validate(skills_only).sections[0].skills == []

    both = _facts_dict()
    both["sections"][0]["skills"] = [
        {"id": "skill.git", "label": "Git", "group": "tools"}
    ]
    validated = CvFacts.model_validate(both)
    assert validated.sections[0].entries
    assert validated.sections[0].skills


def test_resolved_title_maps_a_known_key_and_the_map_is_closed() -> None:
    facts = _facts()

    assert facts.sections[0].resolved_title == SECTION_TITLES["sec.experience"]
    assert facts.sections[0].resolved_title != facts.sections[0].title_key

    with pytest.raises(ValidationError):
        CvFacts.model_validate({**_facts_dict(), "sections": [
            {"id": "s", "title_key": "sec.nope", "order": 1}
        ]})


# --- Test 17: the contact block -----------------------------------------------


def test_contact_round_trips_and_a_partial_contact_is_valid() -> None:
    complete = _facts()
    assert complete.meta.contact is not None
    assert complete.meta.contact.email == "alex.example@example.invalid"
    assert complete.meta.contact.phone is None

    partial = _facts_dict()
    partial["meta"]["contact"] = {"links": ["https://example.invalid/alex"]}
    validated = CvFacts.model_validate(partial)
    assert validated.meta.contact is not None
    assert validated.meta.contact.email is None
    assert validated.meta.contact.links == ["https://example.invalid/alex"]

    without_contact = _facts_dict()
    without_contact["meta"].pop("contact")
    assert CvFacts.model_validate(without_contact).meta.contact is None


def test_the_widened_section_vocabulary_resolves_and_validates() -> None:
    """The three added keys resolve through `resolved_title` and pass the validator.

    The two pre-existing entries are pinned byte-identical and in their original
    order — this change is additive.
    """
    assert SECTION_TITLES["sec.experience"] == "Experience"
    assert SECTION_TITLES["sec.skills"] == "Skills"

    for key in ("sec.projects", "sec.education", "sec.volunteering"):
        section = Section(id=key, title_key=key, order=10)
        assert section.resolved_title == SECTION_TITLES[key]
        assert section.resolved_title != key


def test_meta_accepts_a_location_and_still_rejects_unknown_keys() -> None:
    data = _facts_dict()
    data["meta"]["location"] = "Exampleville, Exampleland"
    assert CvFacts.model_validate(data).meta.location == "Exampleville, Exampleland"

    # Absent is valid and defaults to None.
    assert CvFacts.model_validate(_facts_dict()).meta.location is None

    # `_Forbid` still holds: an unknown meta key is rejected.
    bad = _facts_dict()
    bad["meta"]["bogus_key"] = "surprise"
    with pytest.raises(ValidationError):
        CvFacts.model_validate(bad)


# --- Test 18: the grouped skills render ---------------------------------------


def test_skills_render_as_one_labelled_line_per_group() -> None:
    """Two skills in one group collapse to ONE tabularx row (the golden has one each).

    The fact-equivalence lane does not cover skills, so this is the only guard on the
    grouped render.
    """
    data = _facts_dict()
    data["sections"][1]["skills"] = [
        {"id": "skill.python", "label": "Python", "group": "languages"},
        {"id": "skill.go", "label": "Go", "group": "languages"},
        {"id": "skill.postgresql", "label": "PostgreSQL", "group": "databases"},
    ]

    plan = apply_patch(CvFacts.model_validate(data))
    section = plan.sections[1]

    assert [
        (group, [skill.label for skill in group_skills])
        for group, group_skills in section.skills_by_group
    ] == [("languages", ["Python", "Go"]), ("databases", ["PostgreSQL"])]

    rendered = render_plan_to_tex(plan)
    assert "  languages & Python, Go \\\\" in rendered
    assert "  databases & PostgreSQL \\\\" in rendered
    # Exactly one row per group: the two language skills share a single line.
    assert rendered.count("languages &") == 1
    assert rendered.count("databases &") == 1


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
