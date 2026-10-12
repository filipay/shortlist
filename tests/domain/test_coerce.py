"""G-07-7 — the single-key array-wrapper `{"item": ...}` on every list-typed field.

The provider intermittently encodes a JSON array as a single-key wrapper object
``{"item": <value>}`` (and an empty array as ``""``). The captured drafting payload
carries ``evidence_ids`` as ``{"item": [...]}``; the same class hit tailoring's
``gaps[].evidence_ids == ""``. This module pins the shared unwrap on each
wire-adjacent schema and proves every OTHER shape still fails loudly.

The schemas are imported from their real modules (not the helper) so the positives
here fail on the pre-fix code with the recorded ``list_type`` error.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.cv import GapFinding, Suggestion
from app.domain.schemas.ranking import RankingResponse
from app.domain.schemas.screening import ScreeningAnswer


def test_a_nested_single_key_wrapper_unwraps_to_the_inner_list() -> None:
    answer = ScreeningAnswer.model_validate(
        {
            "question": "Q",
            "answer": "A",
            "evidence_ids": {"item": {"item": ["bul/x/1", "bul/x/2"]}},
        }
    )

    assert answer.evidence_ids == ["bul/x/1", "bul/x/2"]


def test_a_multi_key_mapping_evidence_ids_still_fails_loudly() -> None:
    """Only a single-key wrapper is unwrapped; a 2-key mapping is not a list."""
    with pytest.raises(ValidationError):
        ScreeningAnswer.model_validate(
            {"question": "Q", "answer": "A", "evidence_ids": {"a": 1, "b": 2}}
        )


def test_an_unknown_single_key_wrapper_still_fails_loudly() -> None:
    """`{"nope": 1}` unwraps to the scalar 1, which is not a `list[str]`."""
    with pytest.raises(ValidationError):
        ScreeningAnswer.model_validate(
            {"question": "Q", "answer": "A", "evidence_ids": {"nope": 1}}
        )


def test_a_suggestion_wrapped_evidence_ids_unwraps() -> None:
    suggestion = Suggestion(
        bullet_id="bul/x/1",
        evidence_ids={"item": ["bul/x/1"]},
        rationale="r",
    )

    assert suggestion.evidence_ids == ["bul/x/1"]


def test_a_gap_finding_wrapped_evidence_ids_unwraps() -> None:
    # The tailoring sibling hit `gaps[].evidence_ids == ""`; the wrapper is the same class.
    finding = GapFinding(
        requirement="Terraform",
        status="gap",
        evidence_ids={"item": ["bul/x/1"]},
    )

    assert finding.evidence_ids == ["bul/x/1"]


def test_a_ranking_response_wrapped_requirements_unwraps() -> None:
    response = RankingResponse(
        requirements={"item": [{"text": "Five years Python", "verdict": "gap"}]}
    )

    assert len(response.requirements) == 1
    assert response.requirements[0].text == "Five years Python"
    assert response.requirements[0].verdict == "gap"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
