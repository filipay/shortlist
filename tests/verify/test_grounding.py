"""A1 / D-70 — the advisory grounding band never blocks.

The band is a fuzzy similarity label, so its whole safety property is that it cannot
change ``VerificationResult.passed``. These tests pin the band mapping, the exact
threshold boundaries, and — the load-bearing one — that a ``direct`` finding whose
resolvable evidence bands ``ungrounded`` still passes.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.domain.cv import GapFinding, TailoringPatch, apply_patch
from app.domain.tex import normalise_for_compare
from app.verify import verify_plan
from app.verify.grounding import band_for, evidence_text_for
from tests.verify.fixtures import build_fixture, load_standin_facts

BULLET1 = "bul/northwind-labs-2021/1"
BULLET2 = "bul/northwind-labs-2021/2"
BULLET3 = "bul/northwind-labs-2021/3"


def _facts():
    return load_standin_facts()


# --- the band mapping ----------------------------------------------------------


def test_a_near_verbatim_match_bands_grounded() -> None:
    facts = _facts()
    finding = GapFinding(requirement="Reduced p99 latency", status="direct", evidence_ids=[BULLET1])

    band = band_for(
        finding.requirement,
        evidence_text_for(facts, finding),
        grounded_at=80,
        review_at=55,
    )

    assert band == "grounded"


def test_a_token_overlap_match_bands_borderline_or_ungrounded() -> None:
    facts = _facts()
    finding = GapFinding(
        requirement="Kubernetes orchestration pipelines",
        status="direct",
        evidence_ids=[BULLET2],
    )

    band = band_for(
        finding.requirement,
        evidence_text_for(facts, finding),
        grounded_at=80,
        review_at=55,
    )

    assert band in {"borderline", "ungrounded"}


def test_the_band_boundaries_are_pinned() -> None:
    requirement, evidence = "alpha beta gamma", "alpha beta delta"
    score = int(
        fuzz.token_set_ratio(normalise_for_compare(requirement), normalise_for_compare(evidence))
    )

    assert band_for(requirement, evidence, grounded_at=score, review_at=0) == "grounded"
    assert band_for(requirement, evidence, grounded_at=score + 1, review_at=score) == "borderline"
    assert (
        band_for(requirement, evidence, grounded_at=score + 1, review_at=score + 1) == "ungrounded"
    )


def test_the_fixture_carries_its_expected_bands() -> None:
    """The builder's per-requirement grounding expectation is exercised, not dead."""
    patch = TailoringPatch(
        listing_id=1,
        gaps=[
            GapFinding(
                requirement="Kubernetes orchestration",
                status="direct",
                evidence_ids=[BULLET2],
            )
        ],
    )
    fixture = build_fixture(patch, bands={"Kubernetes orchestration": "ungrounded"})

    finding = fixture.patch.gaps[0]
    computed = band_for(
        finding.requirement,
        evidence_text_for(fixture.facts, finding),
        grounded_at=80,
        review_at=55,
    )

    assert computed == fixture.bands["Kubernetes orchestration"]


# --- the A1 pin: a fuzzy band never flips `passed` -----------------------------


def test_an_ungrounded_band_does_not_block() -> None:
    facts = _facts()
    patch = TailoringPatch(
        listing_id=1,
        gaps=[
            GapFinding(
                requirement="Kubernetes orchestration",
                status="direct",
                evidence_ids=[BULLET3],
            )
        ],
    )
    plan = apply_patch(facts, patch)

    result = verify_plan(facts, plan, patch)

    assert result.passed is True
    check = next(item for item in result.checks if item.id == "requirement_evidence")
    assert check.status == "pass"
    assert "ungrounded" in check.detail


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
