"""D-111..D-115 — the Layer-1 deterministic pre-check.

One case per check: a happy path asserting `passed is True`, then a fixture per
failure class — an id ghost, an unresolvable org, a bullet that vanished with no
drop, a dropped bullet retained in the plan (the reverse direction), a bad date
range, and a `direct` finding with no evidence id. `passed` is a value, never an
exception.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.domain.cv import CvFacts, GapFinding, TailoringPatch, apply_patch
from app.verify import verify_plan
from app.verify.base import VERIFIER_VERSION
from app.verify.plan_checks import (
    check_bullet_conservation,
    check_entity_resolvable,
    check_id_containment,
    check_requirement_evidence,
    check_temporal_consistency,
)
from tests.verify.fixtures import FACTS_YAML, build_fixture, load_standin_facts

BULLET3 = "bul/northwind-labs-2021/3"


def _isolated_plan():
    """A plan deep-copied away from its facts.

    `apply_patch` deliberately carries the SAME `Bullet` objects through, so an
    in-place mutation on a plan would also mutate the fact store. The failure-class
    fixtures must mutate an isolated copy.
    """
    return build_fixture().plan.model_copy(deep=True)


# --- the happy path ------------------------------------------------------------


def test_a_valid_plan_passes_every_layer_one_check() -> None:
    fixture = build_fixture()

    result = verify_plan(fixture.facts, fixture.plan, fixture.patch)

    assert result.passed is True
    assert [check.id for check in result.checks] == [
        "id_containment",
        "entity_resolvable",
        "bullet_conservation",
        "temporal_consistency",
        "requirement_evidence",
    ]
    assert all(check.status == "pass" for check in result.checks)
    assert result.verifier_version == VERIFIER_VERSION


def test_the_committed_extraction_carries_the_facts() -> None:
    """The fixture's `text` is a real extraction, not a placeholder."""
    fixture = build_fixture()

    assert "Northwind Labs" in fixture.text
    assert "Led the migration to a single-writer queue" in fixture.text


# --- id_containment ------------------------------------------------------------


def test_id_containment_fails_on_a_ghost_bullet_id() -> None:
    plan = _isolated_plan()
    plan.sections[0].entries[0].bullets[0].id = "bul/ghost/1"

    result = check_id_containment(load_standin_facts(), plan)

    assert result.status == "fail"
    assert "bul/ghost/1" in result.offending


# --- entity_resolvable ---------------------------------------------------------


def test_entity_resolvable_fails_on_an_org_outside_the_enumerations() -> None:
    plan = _isolated_plan()
    plan.sections[0].entries[0].org = "Ghost Corp"

    result = check_entity_resolvable(load_standin_facts(), plan)

    assert result.status == "fail"
    assert "Ghost Corp" in result.offending


# --- bullet_conservation -------------------------------------------------------


def test_bullet_conservation_fails_when_a_bullet_vanishes_with_no_drop() -> None:
    plan = _isolated_plan()
    entry = plan.sections[0].entries[0]
    entry.bullets = entry.bullets[:2]  # bullet 3 vanished, no drop declared

    result = check_bullet_conservation(
        load_standin_facts(), plan, TailoringPatch(listing_id=1)
    )

    assert result.status == "fail"
    assert BULLET3 in result.offending


def test_bullet_conservation_fails_when_a_declared_drop_was_retained() -> None:
    """The REVERSE direction: a drop declared but not actually applied."""
    from app.domain.cv import DropBullet

    facts = load_standin_facts()
    plan = apply_patch(facts)  # the bullet is still present
    patch = TailoringPatch(
        listing_id=1,
        ops=[DropBullet(op="drop_bullet", bullet_id=BULLET3, reason="irrelevant")],
    )

    result = check_bullet_conservation(facts, plan, patch)

    assert result.status == "fail"
    assert BULLET3 in result.offending


# --- temporal_consistency ------------------------------------------------------


def _facts_with_reversed_dates() -> CvFacts:
    data = yaml.safe_load(Path(FACTS_YAML).read_text(encoding="utf-8"))
    entry = data["sections"][0]["entries"][0]
    entry["end"] = "2019-01"  # before start 2021-03
    return CvFacts.model_validate(data)


def test_temporal_consistency_fails_on_a_reversed_date_range() -> None:
    result = check_temporal_consistency(_facts_with_reversed_dates())

    assert result.status == "fail"


def test_temporal_consistency_fails_when_an_injected_now_is_before_a_start() -> None:
    facts = load_standin_facts()

    result = check_temporal_consistency(facts, now=datetime(2020, 1, 1, tzinfo=UTC))

    assert result.status == "fail"


def test_temporal_consistency_is_clock_free_without_a_now() -> None:
    facts = load_standin_facts()

    assert check_temporal_consistency(facts).status == "pass"


# --- requirement_evidence ------------------------------------------------------


def test_requirement_evidence_fails_on_a_direct_finding_with_no_evidence() -> None:
    facts = load_standin_facts()
    patch = TailoringPatch(
        listing_id=1,
        gaps=[GapFinding(requirement="Rust", status="direct", evidence_ids=[])],
    )

    result = check_requirement_evidence(facts, patch)

    assert result.status == "fail"
    assert result.offending == ["gap[0]"]


def test_requirement_evidence_fails_on_a_gap_with_resolvable_evidence() -> None:
    facts = load_standin_facts()
    patch = TailoringPatch(
        listing_id=1,
        gaps=[GapFinding(requirement="Rust", status="gap", evidence_ids=[BULLET3])],
    )

    result = check_requirement_evidence(facts, patch)

    assert result.status == "fail"


def test_requirement_evidence_accepts_a_grounded_direct_finding() -> None:
    facts = load_standin_facts()
    patch = TailoringPatch(
        listing_id=1,
        gaps=[GapFinding(requirement="Redis", status="direct", evidence_ids=[BULLET3])],
    )

    assert check_requirement_evidence(facts, patch).status == "pass"


def test_the_aggregate_passes_iff_no_check_fails() -> None:
    plan = _isolated_plan()
    plan.sections[0].entries[0].bullets[0].id = "bul/ghost/1"

    result = verify_plan(load_standin_facts(), plan, TailoringPatch(listing_id=1))

    assert result.passed is False


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
