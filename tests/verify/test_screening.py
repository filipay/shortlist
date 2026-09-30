"""D-125 — the deterministic screening-answer grounding check.

Both directions are tested explicitly (CONVENTIONS rule 7): the catch-the-bad
direction (unknown evidence id, novel metric digit) AND the accept-valid direction
(a grounded answer and a legitimate paraphrase that reuses a known digit must pass
clean). CONVENTIONS rule 4 is honoured by the parametrized mutation test below,
which embeds other entities' identifiers into a valid answer and asserts the
checker still passes — a lexical implementation would false-fail it.
"""

from __future__ import annotations

import pytest

from app.domain.cv import iter_fact_ids
from app.domain.schemas.screening import ScreeningAnswer, ScreeningDraftResponse
from app.verify.screening import ground_screening_answers
from tests.verify.fixtures import load_standin_facts

#: A realistic listing text for the grounding corpus.
LISTING_TEXT = (
    "Senior Engineer at Northwind competitor. We build data pipelines and need "
    "Python and PostgreSQL experience."
)

#: A bullet id that exists in the stand-in fact store.
KNOWN_BULLET = "bul/northwind-labs-2021/1"


def _ground(*answers: ScreeningAnswer) -> list:
    return ground_screening_answers(
        load_standin_facts(),
        LISTING_TEXT,
        ScreeningDraftResponse(answers=list(answers)),
    )


# --- accept-valid direction (the false-positive surface) -----------------------


def test_a_grounded_answer_passes_clean() -> None:
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Have you run ingest pipelines?",
            answer="Yes — I rewrote an ingest path to cut latency.",
            evidence_ids=[KNOWN_BULLET],
        )
    )

    assert verdict.unsupported is False
    assert verdict.warnings == []
    assert verdict.grounded_evidence_ids == [KNOWN_BULLET]


def test_a_legitimate_paraphrase_with_a_known_digit_passes_clean() -> None:
    """A number that IS in the sources is not flagged (the false-positive guard)."""
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Quantify an impact.",
            answer="I reduced p99 latency by 40% on the ingest path.",
            evidence_ids=[KNOWN_BULLET],
        )
    )

    assert verdict.unsupported is False, verdict.warnings
    assert verdict.warnings == []


def test_a_known_year_from_the_cv_facts_passes_clean() -> None:
    (verdict,) = _ground(
        ScreeningAnswer(
            question="When did you do that?",
            answer="I did that from 2021 to 2024 at Northwind Labs.",
            evidence_ids=["exp/northwind-labs-2021"],
        )
    )

    assert verdict.unsupported is False, verdict.warnings


def test_an_answer_with_no_evidence_ids_and_no_digits_passes_clean() -> None:
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Are you available?",
            answer="Yes, I can start immediately.",
        )
    )

    assert verdict.unsupported is False
    assert verdict.grounded_evidence_ids == []


# --- catch-the-bad direction (the false-negative surface) ----------------------


def test_an_unknown_evidence_id_is_flagged_and_named() -> None:
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Do you know Kubernetes?",
            answer="Yes, extensively.",
            evidence_ids=["bul/does-not-exist/9", KNOWN_BULLET],
        )
    )

    assert verdict.unsupported is True
    # The real id still grounds; only the unknown one is dropped.
    assert verdict.grounded_evidence_ids == [KNOWN_BULLET]
    assert any("bul/does-not-exist/9" in warning for warning in verdict.warnings), (
        verdict.warnings
    )
    assert any("unsupported evidence id" in warning for warning in verdict.warnings)


def test_a_fabricated_metric_digit_is_flagged_and_named() -> None:
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Quantify a win.",
            answer="I increased revenue by 987654% in one quarter.",
            evidence_ids=[KNOWN_BULLET],
        )
    )

    assert verdict.unsupported is True
    assert any("987654" in warning for warning in verdict.warnings), verdict.warnings
    assert any("unsupported number" in warning for warning in verdict.warnings)


def test_a_novel_digit_absent_only_from_the_listing_is_still_flagged() -> None:
    """The corpus is CV facts PLUS the listing; a digit in neither is novel."""
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Any certifications?",
            answer="I hold 4242 certifications.",
            evidence_ids=[],
        )
    )

    assert verdict.unsupported is True
    assert any("4242" in warning for warning in verdict.warnings)


# --- the advisory band never flips the warning state (prohibition) -------------


def test_the_advisory_band_is_present_but_never_flips_the_warning_state() -> None:
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Describe yourself.",
            answer="Purple monkey dishwasher.",
            evidence_ids=[],
        )
    )

    # The band may read as ungrounded — but the warning state is driven ONLY by the
    # deterministic checks, so a clean answer stays clean.
    assert verdict.band in {"grounded", "borderline", "ungrounded"}
    assert verdict.unsupported is False
    assert verdict.warnings == []


# --- CONVENTIONS rule 4: the failure class, not the instance -------------------

ALL_FACT_IDS = sorted(iter_fact_ids(load_standin_facts()))


@pytest.mark.parametrize("identifier", ALL_FACT_IDS)
def test_embedding_another_entitys_identifier_does_not_false_fail(identifier: str) -> None:
    """A valid answer that also mentions other entities' identifiers stays clean.

    The checker is structurally grounded (byte-exact id set + digit containment),
    never substring containment over free text, so a sibling entry's id/name in the
    answer text cannot hijack it.
    """
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Tell me about your experience.",
            answer=f"I also worked with {identifier} and Northwind Labs on the team.",
            evidence_ids=[KNOWN_BULLET],
        )
    )

    assert verdict.unsupported is False, f"{identifier}: {verdict.warnings}"
    assert verdict.grounded_evidence_ids == [KNOWN_BULLET]


@pytest.mark.parametrize(
    "evidence_id",
    ["skill.python", "org.northwind", "title.senior_engineer", "exp/northwind-labs-2021"],
)
def test_any_real_fact_id_grounds_as_evidence(evidence_id: str) -> None:
    """Grounding is over the whole fact-id set, not bullets only."""
    (verdict,) = _ground(
        ScreeningAnswer(
            question="Evidence?",
            answer="See the CV.",
            evidence_ids=[evidence_id],
        )
    )

    assert verdict.unsupported is False
    assert verdict.grounded_evidence_ids == [evidence_id]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
