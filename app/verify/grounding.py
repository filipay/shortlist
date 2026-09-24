"""The advisory grounding band for check 6 (A1, D-70's rule applied).

The **only** ``rapidfuzz`` consumer in the verifier, mirroring
``app/domain/dedup.py``'s import shape (``from rapidfuzz import fuzz``).

**FUZZY means ADVISORY here, and only here.** This is a similarity ratio, so it must
never be load-bearing on a block decision: a fuzzy threshold on a block is a
false-positive machine (the same argument D-70 makes against a fuzzy membership
ratio). A ``direct`` claim whose cited evidence bands ``ungrounded`` is exactly the
case a human should look at, but it is not provably fabricated, so it rides the
``CheckResult`` as a detail/label and never flips ``VerificationResult.passed``.

**The thresholds are ARGUMENTS, never module literals.** The caller reads them from
``Settings`` (that is what ``tests/test_config.py``'s absence scan over ``app/verify``
exists to enforce), so calibration is a config change (PLAT-04). The shipped 80/55
defaults are UNCALIBRATED against a real CV/listing corpus (A1) and are not presented
as measured.
"""

from __future__ import annotations

from typing import Literal

from rapidfuzz import fuzz

from app.domain.cv import CvFacts, GapFinding
from app.domain.tex import normalise_for_compare

#: The three confidence bands. Advisory labels — none of them blocks.
GroundingBand = Literal["grounded", "borderline", "ungrounded"]


def band_for(
    requirement: str,
    evidence_text: str,
    *,
    grounded_at: int,
    review_at: int,
) -> GroundingBand:
    """Band one requirement's citation by its token-set similarity to its evidence.

    ``grounded`` when the score is at least ``grounded_at``; ``borderline`` when it is
    at least ``review_at`` but below ``grounded_at``; ``ungrounded`` below both. Both
    thresholds are required arguments so no value is hard-coded in this package.
    """
    score = fuzz.token_set_ratio(
        normalise_for_compare(requirement), normalise_for_compare(evidence_text)
    )
    if score >= grounded_at:
        return "grounded"
    if score >= review_at:
        return "borderline"
    return "ungrounded"


def evidence_text_for(facts: CvFacts, finding: GapFinding) -> str:
    """The concatenated ``text`` of a finding's cited evidence bullets.

    Resolves ids through ``facts``; an id that names a non-bullet fact (a skill, an
    entry) contributes nothing here. Total: an unresolvable id is simply absent.
    """
    cited = set(finding.evidence_ids)
    parts = [
        bullet.text
        for entry in facts.all_entries()
        for bullet in entry.bullets
        if bullet.id in cited
    ]
    return "\n".join(parts)


__all__ = ["GroundingBand", "band_for", "evidence_text_for"]
