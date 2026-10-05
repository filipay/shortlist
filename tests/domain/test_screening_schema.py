"""G-07-2 — the screening schema coerce the recorded non-list shapes only.

The UAT recorded live drafting calls that answered with
``validation failed: Input should be a valid list``: the model produced a list-typed
field as something other than a JSON array. These tests pin the schema-local
coercion (a single answer-shaped object, a bare evidence-id string) and prove the
``extra="forbid"`` wire contract and the loud failure on every other shape survive.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.schemas.screening import ScreeningAnswer, ScreeningDraftResponse

#: The recorded malformed shape: `answers` is a single object, not an array, and the
#: nested `evidence_ids` is a bare (comma-separated) string, not an array.
GOLDEN_OBJECT_ANSWERS_PAYLOAD = {
    "answers": {
        "question": "Why this role?",
        "answer": "Because I build pipelines.",
        "evidence_ids": "bul/northwind-labs-2021/1, skill.python",
    }
}


def test_the_recorded_non_list_payload_validates_with_its_answer_intact() -> None:
    result = ScreeningDraftResponse.model_validate(GOLDEN_OBJECT_ANSWERS_PAYLOAD)

    assert len(result.answers) == 1
    assert result.answers[0].question == "Why this role?"
    assert result.answers[0].answer == "Because I build pipelines."
    # The comma-split is the only string interpretation; nothing is dropped.
    assert result.answers[0].evidence_ids == ["bul/northwind-labs-2021/1", "skill.python"]


def test_a_bare_evidence_id_string_becomes_a_one_element_list() -> None:
    answer = ScreeningAnswer.model_validate(
        {"question": "Q", "answer": "A", "evidence_ids": "skill.python"}
    )

    assert answer.evidence_ids == ["skill.python"]


def test_a_none_evidence_ids_becomes_the_empty_list() -> None:
    answer = ScreeningAnswer.model_validate(
        {"question": "Q", "answer": "A", "evidence_ids": None}
    )

    assert answer.evidence_ids == []


def test_a_valid_array_payload_validates_unchanged() -> None:
    payload = {
        "answers": [
            {
                "question": "Q1",
                "answer": "A1",
                "evidence_ids": ["bul/northwind-labs-2021/1"],
            },
            {"question": "Q2", "answer": "A2", "evidence_ids": []},
        ]
    }

    result = ScreeningDraftResponse.model_validate(payload)

    assert [answer.question for answer in result.answers] == ["Q1", "Q2"]
    assert result.answers[0].evidence_ids == ["bul/northwind-labs-2021/1"]


def test_an_unknown_key_still_fails_loudly() -> None:
    """The coercion must not weaken `extra="forbid"` (A4)."""
    with pytest.raises(ValidationError):
        ScreeningDraftResponse.model_validate(
            {"answers": [], "smuggled": "value"}
        )

    with pytest.raises(ValidationError):
        ScreeningAnswer.model_validate(
            {"question": "Q", "answer": "A", "evidence_ids": [], "extra": 1}
        )


def test_a_scalar_answers_value_still_fails_loudly() -> None:
    """Only the recorded shapes are coerced; every other shape keeps failing."""
    with pytest.raises(ValidationError):
        ScreeningDraftResponse.model_validate({"answers": "not-an-answer"})


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
