"""G-07-7 — the single-key array-wrapper `{"item": ...}` on every list-typed field.

The provider intermittently encodes a JSON array as a single-key wrapper object
``{"item": <value>}`` (and an empty array as ``""``). The captured drafting payload
carries ``evidence_ids`` as ``{"item": [...]}``; the same class hit tailoring's
``gaps[].evidence_ids == ""``. This module pins the shared unwrap on each
wire-adjacent schema and proves every OTHER shape still fails loudly.

WR-01: the unwrap is restricted to the literal wrapper key ``"item"``, so the
failure cases below pass a **list** under the unknown key — testing the failure
CLASS (an unknown key), not the scalar instance the earlier cases happened to use
(CONVENTIONS rule 4). The schemas are imported from their real modules (not the
helper) so the positives here fail on the pre-fix code with the recorded
``list_type`` error.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.cv import GapFinding, Suggestion, TailoringPatch
from app.domain.schemas._coerce import unwrap_single_key_mapping
from app.domain.schemas.ranking import RankingResponse
from app.domain.schemas.screening import ScreeningAnswer, ScreeningDraftResponse


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


def test_an_unknown_wrapper_key_with_a_list_value_still_fails_loudly() -> None:
    """Only the literal wrapper key `item` is unwrapped; an unknown key is left to
    pydantic even when its value is a list (the finding's literal repro shape)."""
    assert unwrap_single_key_mapping({"nope": ["bul/x/1"]}) == {"nope": ["bul/x/1"]}

    with pytest.raises(ValidationError):
        ScreeningAnswer.model_validate(
            {"question": "Q", "answer": "A", "evidence_ids": {"nope": ["bul/x/1"]}}
        )


@pytest.mark.parametrize("wrapper_key", ["items", "value", "data"])
def test_a_non_item_single_key_still_fails_loudly(wrapper_key: str) -> None:
    """The key must BE the literal `item`, not merely 'a single key'."""
    with pytest.raises(ValidationError):
        ScreeningAnswer.model_validate(
            {
                "question": "Q",
                "answer": "A",
                "evidence_ids": {wrapper_key: ["bul/x/1"]},
            }
        )


def test_an_unknown_key_on_the_mapping_list_path_fails_via_extra_forbid() -> None:
    """On the `coerce_mapping_list` path an unknown single key fails by a different
    route: an unwrapped Mapping becomes ONE item-shaped object and the item model's
    `extra="forbid"` refuses it."""
    with pytest.raises(ValidationError):
        ScreeningDraftResponse.model_validate(
            {"answers": {"nope": [{"question": "Q", "answer": "A"}]}}
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


# --- IN-01: the tailoring patch's top-level lists share the same helper ---------


@pytest.mark.parametrize(
    ("field", "one_op"),
    [
        ("ops", {"op": "move_bullet", "bullet_id": "bul/acme-ltd-2021/1"}),
        ("gaps", {"requirement": "Terraform", "status": "gap"}),
        ("suggestions", {"bullet_id": "bul/acme-ltd-2021/1", "rationale": "r"}),
    ],
)
def test_a_tailoring_patch_list_field_unwraps_the_wrapper_and_wraps_the_bare_object(
    field: str, one_op: dict
) -> None:
    wrapped = TailoringPatch(listing_id=1, **{field: {"item": [one_op]}})
    bare = TailoringPatch(listing_id=1, **{field: one_op})

    assert len(getattr(wrapped, field)) == 1
    assert len(getattr(bare, field)) == 1


def test_a_tailoring_patch_non_item_single_key_mapping_is_refused() -> None:
    """A bare non-`item` single-key mapping is not unwrapped; it becomes one item and
    the item model refuses it (`extra="forbid"` / a missing required field)."""
    with pytest.raises(ValidationError):
        TailoringPatch(
            listing_id=1, gaps={"nope": [{"requirement": "r", "status": "gap"}]}
        )


# --- IN-02: the loop is bounded (ordered last so a `-x` pre-fix run does not hang) -


def test_a_self_referential_single_key_mapping_terminates() -> None:
    """A caller-constructed `d["item"] = d` must not hang the exported helper."""
    self_referential: dict = {}
    self_referential["item"] = self_referential

    assert unwrap_single_key_mapping(self_referential) is self_referential


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
