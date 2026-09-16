"""Pure Tier-2 dedup decisions (D-31): the safety-biased cross-source merge gate.

No I/O, no session, no settings — every function here is deterministic and
unit-testable. `sqlalchemy` is forbidden under `app.domain`
(`tests/test_import_discipline.py`); `rapidfuzz` and `app.domain.listing` are the
only non-stdlib imports.

Safety bias
-----------
The failure mode this module exists to prevent is not "fails to merge" but
"merges two genuinely different roles" — silent, and it destroys a real job
(PITFALLS P3). So the gate is **component-based and safety-biased**: a pair must
pass four checks — grade, company, location, score — before it may merge.

Token-set ratio is deliberately **not used anywhere in the decision**. It returns
`100.0` when one string is a subset of the other, so `"Software Engineer"` vs
`"Senior Software Engineer"` scores a perfect 100 — the exact P3 failure. The gate
uses `fuzz.token_sort_ratio`, which is *not* subset-forgiving. A caller may compute
the token-set score as a diagnostic for the run log only; it never decides here.

θ is a **parameter**, never a literal: the stage reads it from
`Settings.dedup_fuzzy_threshold`.

Totality: an empty input, a group of one, an unknown/`None` company and a
malformed pair all produce an empty list rather than raising.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from rapidfuzz import fuzz

#: Grade/level tokens that make two otherwise-identical titles different roles.
#: `senior` vs no token, and `ii` vs `senior`, must never merge — whatever the
#: fuzzy score says (PITFALLS P3) — so this guard sits on the decision path.
GRADE_TOKENS = frozenset(
    {
        "senior",
        "sr",
        "lead",
        "staff",
        "principal",
        "head",
        "chief",
        "junior",
        "jr",
        "intern",
        "internship",
        "graduate",
        "trainee",
        "i",
        "ii",
        "iii",
        "iv",
    }
)

#: The method recorded on a merge this module planned. It is a literal because
#: `listing_dupes.method` is free text and the audit view groups by it.
METHOD_FUZZY_TUPLE = "fuzzy_tuple"


@dataclass(frozen=True)
class CandidateFacts:
    """The subset of a `listings` row the dedup decision needs. Pure values."""

    listing_id: int
    company_norm: str | None
    title_norm: str
    location_norm: str | None
    blocking_key: str | None
    posted_at: datetime | None
    first_seen_at: datetime


@dataclass(frozen=True)
class MergeDecision:
    """One pair that may merge: the earliest-seen listing absorbs the other."""

    survivor_id: int
    absorbed_id: int
    score: float
    method: str


def _grade_tokens(title_norm: str | None) -> frozenset[str]:
    return frozenset(token for token in (title_norm or "").split() if token in GRADE_TOKENS)


def grades_conflict(title_norm_a: str | None, title_norm_b: str | None) -> bool:
    """True when the two titles disagree on seniority grade.

    True when exactly one side carries a grade token, or when both carry grade
    tokens that differ. This is the cheapest defence against the P3 over-merge and
    it belongs on the decision path, not in the repository: a pair refused here
    can never merge, however high the fuzzy score.
    """
    grades_a = _grade_tokens(title_norm_a)
    grades_b = _grade_tokens(title_norm_b)
    if not grades_a and not grades_b:
        return False
    return grades_a != grades_b


def _pair_text(facts: CandidateFacts, *, include_location: bool = True) -> str:
    """The normalised tuple as one string, for whichever score is being taken.

    Includes `location_norm` by default — the `(company, title, location)` tuple.
    `include_location=False` drops the location component, which `score_pair` uses
    when exactly one side's location is unknown: the location gate has already
    accepted that pair, so the score must not re-penalise the missing value.
    """
    parts = (facts.company_norm or "", facts.title_norm or "")
    if include_location:
        parts = (*parts, facts.location_norm or "")
    return " ".join(part for part in parts if part)


def score_pair(
    a: CandidateFacts,
    b: CandidateFacts,
    *,
    threshold: int,
    company_threshold: int | None = None,
) -> float | None:
    """The primary gate. Returns the token-sort score when the pair may merge.

    All four checks must pass, in this order:

    1. **grade** — `grades_conflict` refuses outright.
    2. **company** — equal `company_norm`, or `fuzz.token_sort_ratio(company_a,
       company_b) >= company_threshold`. The threshold defaults to `threshold`
       deliberately: a second fuzzy constant would be a knob nobody tunes, and the
       candidate pool is already blocked by company equality in
       `candidate_merges`. An unknown (`None`) company on either side never merges.
    3. **location** — equal `location_norm`, **or either side is `None`** (an
       unknown location is never a rejection reason).
    4. **score** — `token_sort_ratio` over the concatenated normalised tuple must
       be `>= threshold`. When exactly one side's location is `None` the location
       component is excluded from both texts, so the check at 3 does not leak
       into the score as a second, hidden penalty.

    Returns `None` when the pair must not merge; otherwise the score, for the log.
    """
    if grades_conflict(a.title_norm, b.title_norm):
        return None

    if a.company_norm is None or b.company_norm is None:
        return None
    if a.company_norm != b.company_norm:
        limit = threshold if company_threshold is None else company_threshold
        if fuzz.token_sort_ratio(a.company_norm, b.company_norm) < limit:
            return None

    if (
        a.location_norm is not None
        and b.location_norm is not None
        and a.location_norm != b.location_norm
    ):
        return None

    # The location gate above has already refused incompatible *known* locations,
    # so a one-sided unknown location must not also depress the score: the
    # module's contract is that an unknown location is never a rejection reason.
    # Score over `(company, title)` alone when exactly one side is unknown; when
    # both locations are known, keep the full `(company, title, location)` tuple
    # so existing scores are unchanged. (Both-unknown is identical either way —
    # the empty location contributes nothing — so this stays total.)
    include_location = a.location_norm is not None and b.location_norm is not None
    score = fuzz.token_sort_ratio(
        _pair_text(a, include_location=include_location),
        _pair_text(b, include_location=include_location),
    )
    if score < threshold:
        return None
    return float(score)


def _within_window(a: datetime | None, b: datetime | None, *, posted_window_days: int) -> bool:
    """True when the two posted dates are close enough to compare.

    An unknown (`None`) date on either side **passes** — an absent value is never a
    rejection reason (the resolved A2/A3 policy). An uncomparable pair (mixed
    tz-awareness) also passes, for the same reason.
    """
    if a is None or b is None:
        return True
    try:
        return abs(a - b) <= timedelta(days=posted_window_days)
    except TypeError:  # pragma: no cover — mixed naive/aware datetimes
        return True


def candidate_merges(
    facts: Iterable[CandidateFacts],
    *,
    threshold: int,
    posted_window_days: int,
) -> list[MergeDecision]:
    """The pure plan: which pairs may merge, and who survives.

    Candidates are grouped by `company_norm` (an unknown company never merges and
    a group of one is dropped). Pairs are considered in a deterministic order —
    ascending `(survivor.first_seen_at, survivor.listing_id, absorbed.listing_id)`
    — and a listing already absorbed is removed from the pool, so a three-way
    duplicate produces two merges onto the first-seen survivor rather than a
    chain. The earliest-seen listing is always the survivor (D-27).
    """
    items = [item for item in (facts or ()) if isinstance(item, CandidateFacts)]
    groups: dict[str, list[CandidateFacts]] = {}
    for item in items:
        if item.company_norm:
            groups.setdefault(item.company_norm, []).append(item)

    decisions: list[MergeDecision] = []
    absorbed: set[int] = set()

    # Deterministic group order, independent of the caller's iteration order.
    for company_norm in sorted(groups):
        group = groups[company_norm]
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda item: (item.first_seen_at, item.listing_id))
        for index, survivor in enumerate(ordered):
            if survivor.listing_id in absorbed:
                continue
            for twin in ordered[index + 1 :]:
                if twin.listing_id in absorbed:
                    continue
                if not _within_window(
                    survivor.posted_at, twin.posted_at, posted_window_days=posted_window_days
                ):
                    continue
                score = score_pair(survivor, twin, threshold=threshold)
                if score is None:
                    continue
                decisions.append(
                    MergeDecision(
                        survivor_id=survivor.listing_id,
                        absorbed_id=twin.listing_id,
                        score=score,
                        method=METHOD_FUZZY_TUPLE,
                    )
                )
                absorbed.add(twin.listing_id)

    return decisions


__all__ = [
    "GRADE_TOKENS",
    "METHOD_FUZZY_TUPLE",
    "CandidateFacts",
    "MergeDecision",
    "candidate_merges",
    "grades_conflict",
    "score_pair",
]
