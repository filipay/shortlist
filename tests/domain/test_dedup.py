"""QUEUE-03 / D-31 — the safety-biased Tier-2 gate, in depth.

The failure this lane exists to name is *over-merging*: two genuinely different
roles collapsed into one, silently, destroying a real job (PITFALLS P3). Every test
here is a refusal the gate must make, or a determinism property a merge plan needs.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from rapidfuzz import fuzz

from app.domain.dedup import (
    GRADE_TOKENS,
    CandidateFacts,
    MergeDecision,
    candidate_merges,
    grades_conflict,
    score_pair,
)

THETA = 88


def _facts(
    listing_id: int = 1,
    company_norm: str | None = "acme",
    title_norm: str = "software engineer",
    location_norm: str | None = "dublin, ireland",
    posted_at: datetime | None = datetime(2026, 9, 1),
    first_seen_at: datetime = datetime(2026, 9, 1),
    sources: frozenset[str] = frozenset(),
) -> CandidateFacts:
    return CandidateFacts(
        listing_id=listing_id,
        company_norm=company_norm,
        title_norm=title_norm,
        location_norm=location_norm,
        blocking_key=None,
        posted_at=posted_at,
        first_seen_at=first_seen_at,
        sources=sources,
    )


def _text(facts: CandidateFacts) -> str:
    return " ".join(
        part
        for part in (facts.company_norm or "", facts.title_norm or "", facts.location_norm or "")
        if part
    )


# --- the P3 pathology, refused by the grade guard -----------------------------
def test_grade_tokens_cover_the_level_vocabulary() -> None:
    assert {"senior", "sr", "lead", "staff", "principal", "head", "chief"} <= GRADE_TOKENS
    assert {"junior", "jr", "intern", "internship", "graduate", "trainee"} <= GRADE_TOKENS
    assert {"i", "ii", "iii", "iv"} <= GRADE_TOKENS


def test_senior_versus_ungraded_never_merges() -> None:
    senior = _facts(title_norm="senior software engineer")
    plain = _facts(title_norm="software engineer")

    # The refusal is the GUARD's, not a low score.
    assert grades_conflict("senior software engineer", "software engineer") is True
    assert grades_conflict("software engineer", "senior software engineer") is True
    assert score_pair(senior, plain, threshold=THETA) is None
    assert score_pair(plain, senior, threshold=THETA) is None


def test_two_different_grades_never_merge() -> None:
    second = _facts(title_norm="software engineer ii")
    senior = _facts(title_norm="senior software engineer")

    assert grades_conflict("software engineer ii", "senior software engineer") is True
    assert score_pair(second, senior, threshold=THETA) is None


def test_token_set_ratio_is_subset_forgiving_and_is_never_the_gate() -> None:
    """Executable evidence for why the gate uses token_sort_ratio, not token-set."""
    # The canonical subset example from the rapidfuzz docs.
    assert fuzz.token_set_ratio("fuzzy was a bear but not a dog", "fuzzy was a bear") == 100.0

    # The same pathology over the real normalised tuple.
    plain = _facts(title_norm="software engineer")
    senior = _facts(title_norm="senior software engineer")
    assert fuzz.token_set_ratio(_text(plain), _text(senior)) == 100.0

    # ... and the gate still refuses the pair.
    assert score_pair(plain, senior, threshold=THETA) is None


# --- the shared-source identity guard (the 6-of-7 precision fix) ---------------
#
# Tier-1 defines job identity per source (`UNIQUE (source, source_listing_id)`), so
# two distinct listings that share a source are already different jobs and no
# fuzzy score may merge them. A refused duplicate is a VISIBLE duplicate; a wrong
# merge is an INVISIBLE lost job — the documented worst failure mode (P3). Each
# test below pins one shape from the real 7-merge corpus.


def test_identical_title_same_source_different_job_id_never_merges() -> None:
    """Shape #5: identical title, same board, different Indeed `jk`.

    The case no threshold can catch — the titles are byte-identical — so only the
    identity guard can separate the two listings.
    """
    a = _facts(
        listing_id=1,
        company_norm="mastercard",
        title_norm="senior software engineer",
        sources=frozenset({"indeed"}),
    )
    b = _facts(
        listing_id=2,
        company_norm="mastercard",
        title_norm="senior software engineer",
        sources=frozenset({"indeed"}),
    )

    # The tuple is a perfect match — without the guard this WOULD merge.
    assert score_pair(a, b, threshold=THETA) is None


def test_trailing_specialisation_on_one_side_same_source_never_merges() -> None:
    """Shape #2: `Lead Software Engineer - Python` vs `Lead Software Engineer`."""
    specialised = _facts(
        listing_id=1,
        company_norm="jpmorganchase",
        title_norm="lead software engineer - python",
        sources=frozenset({"indeed"}),
    )
    plain = _facts(
        listing_id=2,
        company_norm="jpmorganchase",
        title_norm="lead software engineer",
        sources=frozenset({"indeed"}),
    )

    assert score_pair(specialised, plain, threshold=THETA) is None
    assert score_pair(plain, specialised, threshold=THETA) is None


def test_trailing_different_specialisations_both_sides_same_source_never_merge() -> None:
    """Shape #6: `… - Platform team` vs `… - Team Agent` on the same board."""
    platform = _facts(
        listing_id=1,
        company_norm="taktile",
        title_norm="senior full-stack engineer - platform team",
        sources=frozenset({"linkedin"}),
    )
    agent = _facts(
        listing_id=2,
        company_norm="taktile",
        title_norm="senior full-stack engineer - team agent",
        sources=frozenset({"linkedin"}),
    )

    # Both carry the same grade, so `grades_conflict` cannot separate them and the
    # score is high; only the shared source refuses the pair.
    assert grades_conflict(platform.title_norm, agent.title_norm) is False
    assert score_pair(platform, agent, threshold=THETA) is None


def test_parenthetical_disambiguator_on_one_side_same_source_never_merges() -> None:
    """Shape #3: `Lead Site Reliability Engineer (DSS)` vs the unqualified role."""
    disambiguated = _facts(
        listing_id=1,
        company_norm="jpmorganchase",
        title_norm="lead site reliability engineer (dss)",
        sources=frozenset({"indeed"}),
    )
    plain = _facts(
        listing_id=2,
        company_norm="jpmorganchase",
        title_norm="lead site reliability engineer",
        sources=frozenset({"indeed"}),
    )

    assert score_pair(disambiguated, plain, threshold=THETA) is None
    assert score_pair(plain, disambiguated, threshold=THETA) is None


def test_same_parenthetical_both_sides_different_req_url_same_source_never_merges() -> None:
    """Shape #1: same title and parenthetical, different `dowjones.jobs` req id."""
    first = _facts(
        listing_id=1,
        company_norm="dow jones",
        title_norm="senior qa automation engineer (ai-first)",
        sources=frozenset({"indeed"}),
    )
    second = _facts(
        listing_id=2,
        company_norm="dow jones",
        title_norm="senior qa automation engineer (ai-first)",
        sources=frozenset({"indeed"}),
    )

    assert score_pair(first, second, threshold=THETA) is None


def test_cross_source_near_identical_tuple_still_merges() -> None:
    """Shape #7 (the control): the SAME Mastercard role on Indeed and LinkedIn.

    Cross-source dedup is the whole reason Tier-2 exists; the identity guard must
    not disable it.
    """
    indeed = _facts(
        listing_id=1,
        company_norm="mastercard",
        title_norm="senior software engineer",
        sources=frozenset({"indeed"}),
    )
    linkedin = _facts(
        listing_id=2,
        company_norm="mastercard",
        title_norm="senior software engineer",
        sources=frozenset({"linkedin"}),
    )

    assert score_pair(indeed, linkedin, threshold=THETA) == 100.0
    assert score_pair(linkedin, indeed, threshold=THETA) == 100.0


def test_overlapping_provenance_refuses_a_different_job_id() -> None:
    """A survivor `{indeed, linkedin}` vs a fresh `{indeed}` listing.

    The intersection is non-empty, so the fresh listing is a different Indeed job
    and must not be absorbed into the multi-source survivor.
    """
    survivor = _facts(
        listing_id=1,
        company_norm="acme",
        title_norm="senior python engineer",
        sources=frozenset({"indeed", "linkedin"}),
    )
    fresh = _facts(
        listing_id=2,
        company_norm="acme",
        title_norm="senior python engineer",
        sources=frozenset({"indeed"}),
    )

    assert score_pair(survivor, fresh, threshold=THETA) is None
    assert score_pair(fresh, survivor, threshold=THETA) is None


def test_an_empty_source_set_on_either_side_never_refuses() -> None:
    """Missing provenance must fall through to the score, not disable the merge."""
    known = _facts(
        listing_id=1,
        company_norm="acme",
        title_norm="senior python engineer",
        sources=frozenset({"indeed"}),
    )
    unknown = _facts(
        listing_id=2,
        company_norm="acme",
        title_norm="senior python engineer",
        sources=frozenset(),
    )

    # The guard does NOT refuse an unknown-provenance side; an exact company+title
    # scores 100 through the remaining gates.
    assert score_pair(known, unknown, threshold=THETA) == 100.0
    assert score_pair(unknown, known, threshold=THETA) == 100.0

    # Both unknown is the same story.
    assert score_pair(unknown, unknown, threshold=THETA) == 100.0


# --- regressions the identity guard must not change ----------------------------

def test_the_grade_guard_still_refuses_across_disjoint_sources() -> None:
    """Disjoint sources let the pair reach the next gate, which still refuses it."""
    senior = _facts(
        listing_id=1,
        title_norm="senior software engineer",
        sources=frozenset({"indeed"}),
    )
    plain = _facts(
        listing_id=2,
        title_norm="software engineer",
        sources=frozenset({"linkedin"}),
    )

    assert grades_conflict(senior.title_norm, plain.title_norm) is True
    assert score_pair(senior, plain, threshold=THETA) is None
    assert score_pair(plain, senior, threshold=THETA) is None


def test_a_one_sided_unknown_location_still_merges_across_disjoint_sources() -> None:
    """The `a51a133` behaviour survives the new first check."""
    located = _facts(
        listing_id=1,
        company_norm="mastercard",
        title_norm="senior software engineer",
        location_norm="dublin, d, ie",
        sources=frozenset({"indeed"}),
    )
    locationless = _facts(
        listing_id=2,
        company_norm="mastercard",
        title_norm="senior software engineer",
        location_norm=None,
        sources=frozenset({"linkedin"}),
    )

    assert score_pair(located, locationless, threshold=THETA) == 100.0
    assert score_pair(locationless, located, threshold=THETA) == 100.0


def test_theta_remains_a_parameter_for_cross_source_pairs() -> None:
    """The source guard must not shortcut the score gate."""
    a = _facts(
        listing_id=1,
        company_norm="acme",
        title_norm="senior python engineer",
        location_norm="dublin",
        sources=frozenset({"indeed"}),
    )
    b = _facts(
        listing_id=2,
        company_norm="acme",
        title_norm="senior python developer",
        location_norm="dublin",
        sources=frozenset({"linkedin"}),
    )

    raw = int(fuzz.token_sort_ratio(_text(a), _text(b)))
    assert raw > 0

    assert score_pair(a, b, threshold=raw) is not None
    assert score_pair(a, b, threshold=raw + 1) is None


# --- the whole 7-merge corpus, reproduced --------------------------------------

#: The real corpus's seven candidate pairs. Only #7 is cross-source: it is the
#: single merge the plan must still make. Every other pair shares a board.


def _corpus() -> list[CandidateFacts]:
    """The 7-pair corpus as `CandidateFacts`, faithful to the observed rows."""
    return [
        # #1 dow jones: same title, both indeed, two req URLs -> refuse.
        _facts(
            listing_id=101,
            company_norm="dow jones",
            title_norm="senior qa automation engineer (ai-first)",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 1),
            sources=frozenset({"indeed"}),
        ),
        _facts(
            listing_id=102,
            company_norm="dow jones",
            title_norm="senior qa automation engineer (ai-first)",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 2),
            sources=frozenset({"indeed"}),
        ),
        # #2 jpmorganchase: trailing "- Python" on one side, both indeed -> refuse.
        _facts(
            listing_id=201,
            company_norm="jpmorganchase",
            title_norm="lead software engineer - python",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 1),
            sources=frozenset({"indeed"}),
        ),
        _facts(
            listing_id=202,
            company_norm="jpmorganchase",
            title_norm="lead software engineer",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 2),
            sources=frozenset({"indeed"}),
        ),
        # #3 jpmorganchase: parenthetical on one side, both indeed -> refuse.
        _facts(
            listing_id=203,
            company_norm="jpmorganchase",
            title_norm="lead site reliability engineer (dss)",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 1),
            sources=frozenset({"indeed"}),
        ),
        _facts(
            listing_id=204,
            company_norm="jpmorganchase",
            title_norm="lead site reliability engineer",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 2),
            sources=frozenset({"indeed"}),
        ),
        # #4 jpmorganchase: different parenthetical, both indeed -> refuse.
        _facts(
            listing_id=205,
            company_norm="jpmorganchase",
            title_norm="lead software engineer (backend, aws)",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 1),
            sources=frozenset({"indeed"}),
        ),
        _facts(
            listing_id=206,
            company_norm="jpmorganchase",
            title_norm="lead software engineer- backend",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 2),
            sources=frozenset({"indeed"}),
        ),
        # #5 mastercard: identical title, both indeed, different jk -> refuse.
        _facts(
            listing_id=301,
            company_norm="mastercard",
            title_norm="senior software engineer",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 1),
            sources=frozenset({"indeed"}),
        ),
        _facts(
            listing_id=302,
            company_norm="mastercard",
            title_norm="senior software engineer",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 2),
            sources=frozenset({"indeed"}),
        ),
        # #7 mastercard: the SAME role on linkedin -> the one merge to keep.
        _facts(
            listing_id=303,
            company_norm="mastercard",
            title_norm="senior software engineer",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 3),
            sources=frozenset({"linkedin"}),
        ),
        # #6 taktile: different trailing specialisations, both linkedin -> refuse.
        _facts(
            listing_id=401,
            company_norm="taktile",
            title_norm="senior full-stack engineer - platform team",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 1),
            sources=frozenset({"linkedin"}),
        ),
        _facts(
            listing_id=402,
            company_norm="taktile",
            title_norm="senior full-stack engineer - team agent",
            location_norm=None,
            posted_at=None,
            first_seen_at=datetime(2026, 9, 2),
            sources=frozenset({"linkedin"}),
        ),
    ]


def test_the_real_corpus_yields_exactly_one_cross_source_merge() -> None:
    """With all 7 pairs present, the plan must make ONE merge, not seven."""
    decisions = candidate_merges(_corpus(), threshold=THETA, posted_window_days=90)

    assert len(decisions) == 1, [decision for decision in decisions]
    only = decisions[0]
    assert only.survivor_id == 301, "the earliest-seen Indeed Mastercard listing"
    assert only.absorbed_id == 303, "the cross-source LinkedIn twin"
    assert only.method == "fuzzy_tuple"


# --- the company gate ---------------------------------------------------------
def test_equal_company_passes_and_a_different_company_fails() -> None:
    a = _facts(company_norm="acme")
    b = _facts(company_norm="acme")
    assert score_pair(a, b, threshold=THETA) is not None

    other = _facts(company_norm="globex")
    assert fuzz.token_sort_ratio("acme", "globex") < THETA
    assert score_pair(a, other, threshold=THETA) is None


def test_two_unknown_companies_never_merge() -> None:
    a = _facts(company_norm=None)
    b = _facts(company_norm=None)

    assert score_pair(a, b, threshold=THETA) is None


def test_a_fuzzy_company_within_the_company_threshold_passes() -> None:
    a = _facts(company_norm="acme limited")
    b = _facts(company_norm="acme ltd")

    assert (
        score_pair(a, b, threshold=THETA, company_threshold=60) is not None
    )
    assert score_pair(a, b, threshold=THETA, company_threshold=100) is None


# --- the location gate --------------------------------------------------------
def test_location_gate_allows_equal_or_unknown_and_refuses_a_mismatch() -> None:
    # A permissive theta isolates the LOCATION gate: an unknown side is allowed,
    # a real mismatch is refused regardless of how high the score would be.
    permissive = 50

    assert score_pair(_facts(), _facts(), threshold=permissive) is not None
    assert (
        score_pair(_facts(location_norm=None), _facts(), threshold=permissive) is not None
    )
    assert (
        score_pair(_facts(), _facts(location_norm=None), threshold=permissive) is not None
    )

    far = _facts(location_norm="cork, ireland")
    assert score_pair(_facts(), far, threshold=permissive) is None


# --- a one-sided unknown location must not depress the score ------------------
def test_a_one_sided_unknown_location_is_not_penalised_in_the_score() -> None:
    """The live-corpus shape: an unknown location is compatible, not a penalty.

    `_pair_text` folds `location_norm` into the scored text, so a NULL location
    used to drop a same-company/same-title pair below theta even though the
    location gate immediately above had already accepted it — the module's own
    contract is that an unknown location is never a rejection reason.
    """
    located = _facts(
        company_norm="mastercard",
        title_norm="senior software engineer",
        location_norm="dublin, d, ie",
    )
    locationless = _facts(
        company_norm="mastercard",
        title_norm="senior software engineer",
        location_norm=None,
    )

    # The old computation — location folded into both texts — is exactly what
    # refused the live pair: 83.33 < theta.
    assert fuzz.token_sort_ratio(_text(located), _text(locationless)) < THETA

    # Dropping the location from the score leaves the identical company+title.
    assert score_pair(located, locationless, threshold=THETA) == 100.0
    # Symmetric: either side may be the location-less one.
    assert score_pair(locationless, located, threshold=THETA) == 100.0


def test_the_location_gate_still_refuses_two_known_incompatible_locations() -> None:
    """A known mismatch is still a rejection, whatever the score would be."""
    here = _facts(company_norm="acme", title_norm="python engineer", location_norm="dublin 1")
    there = _facts(company_norm="acme", title_norm="python engineer", location_norm="dublin 2")

    # A permissive theta isolates the gate: only the location check can refuse.
    assert score_pair(here, there, threshold=50) is None
    assert score_pair(there, here, threshold=50) is None


def test_two_known_compatible_locations_still_score_with_location_included() -> None:
    """Guard the "always drop location" regression on the both-present path.

    When both sides carry a location the score must remain the one derived from
    the full `(company, title, location)` tuple — unchanged from before the fix.
    """
    a = _facts(company_norm="acme", title_norm="data engineer", location_norm="dublin, ireland")
    b = _facts(company_norm="acme", title_norm="data engineering", location_norm="dublin, ireland")

    with_location = fuzz.token_sort_ratio(_text(a), _text(b))
    company_title_only = fuzz.token_sort_ratio("acme data engineer", "acme data engineering")
    # The two computations genuinely differ here, so this is a real guard.
    assert with_location != company_title_only
    assert with_location >= THETA

    assert score_pair(a, b, threshold=THETA) == with_location


# --- the score gate boundary --------------------------------------------------
def test_score_gate_at_the_threshold_passes_and_just_below_fails() -> None:
    a = _facts(company_norm="acme", title_norm="python engineer", location_norm="dublin")
    b = _facts(company_norm="acme", title_norm="python developer", location_norm="dublin")

    raw = fuzz.token_sort_ratio(_text(a), _text(b))
    at = int(raw)
    below = at + 1
    assert at > 0

    assert score_pair(a, b, threshold=at) is not None
    assert score_pair(a, b, threshold=below) is None


# --- the posted window --------------------------------------------------------
def test_posted_window_refuses_a_pair_outside_it_and_passes_an_unknown() -> None:
    early = _facts(listing_id=1, first_seen_at=datetime(2026, 1, 1), posted_at=datetime(2026, 1, 1))
    late = _facts(listing_id=2, first_seen_at=datetime(2026, 1, 2), posted_at=datetime(2026, 12, 1))

    assert candidate_merges([early, late], threshold=THETA, posted_window_days=90) == []
    assert len(candidate_merges([early, late], threshold=THETA, posted_window_days=400)) == 1

    unknown = _facts(listing_id=2, first_seen_at=datetime(2026, 1, 2), posted_at=None)
    decisions = candidate_merges([early, unknown], threshold=THETA, posted_window_days=90)
    assert [decision.survivor_id for decision in decisions] == [1]


# --- determinism, ordering and the chain rule ---------------------------------
def test_a_three_way_duplicate_merges_onto_the_first_seen_survivor_without_chaining() -> None:
    first = _facts(listing_id=1, first_seen_at=datetime(2026, 9, 1))
    second = _facts(listing_id=2, first_seen_at=datetime(2026, 9, 2))
    third = _facts(listing_id=3, first_seen_at=datetime(2026, 9, 3))

    decisions = candidate_merges([third, first, second], threshold=THETA, posted_window_days=90)

    assert [decision.survivor_id for decision in decisions] == [1, 1]
    assert [decision.absorbed_id for decision in decisions] == [2, 3]
    assert {decision.method for decision in decisions} == {"fuzzy_tuple"}


def test_the_earliest_seen_listing_is_always_the_survivor() -> None:
    old = _facts(listing_id=7, first_seen_at=datetime(2026, 8, 1))
    new = _facts(listing_id=9, first_seen_at=datetime(2026, 8, 2))

    decisions = candidate_merges([new, old], threshold=THETA, posted_window_days=90)

    assert decisions == [
        MergeDecision(survivor_id=7, absorbed_id=9, score=decisions[0].score, method="fuzzy_tuple")
    ]


def test_shuffled_input_produces_the_same_ordered_decisions() -> None:
    facts = [
        _facts(listing_id=index, first_seen_at=datetime(2026, 9, index)) for index in (1, 2, 3)
    ]

    forward = candidate_merges(facts, threshold=THETA, posted_window_days=90)
    backward = candidate_merges(list(reversed(facts)), threshold=THETA, posted_window_days=90)

    assert forward == backward


# --- totality -----------------------------------------------------------------
def test_total_on_empty_single_and_unknown_company_inputs() -> None:
    assert candidate_merges([], threshold=THETA, posted_window_days=90) == []
    assert candidate_merges([_facts()], threshold=THETA, posted_window_days=90) == []
    assert (
        candidate_merges(
            [_facts(listing_id=1, company_norm=None), _facts(listing_id=2, company_norm=None)],
            threshold=THETA,
            posted_window_days=90,
        )
        == []
    )


def test_an_unsorted_first_seen_is_handled_rather_than_raising() -> None:
    """A pair seen out of order still yields the earlier listing as survivor."""
    later = _facts(listing_id=2, first_seen_at=datetime(2026, 9, 5))
    earlier = _facts(listing_id=1, first_seen_at=datetime(2026, 9, 5) - timedelta(days=1))

    decisions = candidate_merges([later, earlier], threshold=THETA, posted_window_days=90)

    assert len(decisions) == 1
    assert decisions[0].survivor_id == earlier.listing_id
