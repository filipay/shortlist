"""RANK-01 / RANK-02 / RANK-03 — the rubric is pure, ordered and total.

The factor set and its order are the fairness control, so they are pinned
literally. The weighted mean is re-normalised over the factors a listing actually
has, so a missing salary never reads as a bad salary (D-85), and a zero
denominator is an absent total rather than an exception (D-79).
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.domain.rubric import (
    DEFAULT_WEIGHTS,
    FACTORS,
    RUBRIC_VERSION,
    confidence_tier,
    present_factors,
    weighted_total,
)
from app.domain.schemas.ranking import RankingResponse

MODULE_PATH = Path(__file__).resolve().parents[2] / "app" / "domain" / "rubric.py"

#: The six factors exactly as the plan fixes them, in order (D-82).
EXPECTED_FACTORS = (
    "skills",
    "seniority",
    "domain",
    "location",
    "evidence",
    "compensation",
)

FORBIDDEN_IMPORTS = frozenset({"httpx", "sqlalchemy", "jobspy", "jinja2", "subprocess", "fastapi"})


def test_the_factor_set_is_exactly_the_six_in_order() -> None:
    assert FACTORS == EXPECTED_FACTORS


def test_the_rubric_version_is_the_hand_bumped_v1() -> None:
    assert RUBRIC_VERSION == "v1"


def test_every_factor_has_a_default_weight_of_one() -> None:
    assert set(DEFAULT_WEIGHTS) == set(EXPECTED_FACTORS)
    assert all(value == 1.0 for value in DEFAULT_WEIGHTS.values())


def test_the_module_imports_no_io_module_and_not_settings() -> None:
    imported: set[str] = set()
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imported.add(node.module.split(".")[0])

    assert imported & FORBIDDEN_IMPORTS == set()
    assert "app" not in imported, "rubric must stay pure and must not read Settings"


# --- the weighted mean (D-79) --------------------------------------------------


def test_weighted_total_renormalises_over_present_factors() -> None:
    total = weighted_total({"skills": 1.0, "domain": 0.0}, {"skills": 1.0, "domain": 1.0})

    assert total == 0.5


def test_weighted_total_ignores_absent_factors_in_the_denominator() -> None:
    """A missing ``compensation`` re-normalises over the remaining weights."""
    total = weighted_total(
        {"skills": 0.5, "domain": 0.5}, {"skills": 1.0, "domain": 1.0, "compensation": 3.0}
    )

    assert total == 0.5, "an absent factor must not drag the denominator down"


def test_weighted_total_honours_the_weights() -> None:
    total = weighted_total({"skills": 1.0, "domain": 0.0}, {"skills": 3.0, "domain": 1.0})

    assert total == 0.75


def test_weighted_total_is_none_for_an_all_zero_weight_set() -> None:
    assert weighted_total({"skills": 1.0}, {"skills": 0.0}) is None


def test_weighted_total_is_none_for_an_empty_sub_score_mapping() -> None:
    assert weighted_total({}, {"skills": 1.0}) is None


def test_weighted_total_keeps_a_present_zero_and_never_treats_it_as_absent() -> None:
    """0.0 is a real sub-score; the -1.0 sentinel is the absent one (D-85)."""
    assert present_factors({"skills": 0.0}) == ("skills",)
    assert present_factors({"skills": -1.0}) == ()
    assert weighted_total({"skills": 0.0}, {"skills": 1.0}) == 0.0


# --- the confidence tier (D-85) ------------------------------------------------


def test_confidence_tier_high_when_all_six_are_present() -> None:
    assert confidence_tier({factor: 0.5 for factor in EXPECTED_FACTORS}) == "high"


def test_confidence_tier_medium_at_four_and_five() -> None:
    four = {factor: 0.5 for factor in EXPECTED_FACTORS[:4]}
    five = {factor: 0.5 for factor in EXPECTED_FACTORS[:5]}

    assert confidence_tier(four) == "medium"
    assert confidence_tier(five) == "medium"


def test_confidence_tier_low_below_four() -> None:
    three = {factor: 0.5 for factor in EXPECTED_FACTORS[:3]}

    assert confidence_tier(three) == "low"
    assert confidence_tier({}) == "low"


# --- the response schema (D-78) ------------------------------------------------


def test_the_schema_exposes_six_top_level_factors_and_no_total() -> None:
    schema = RankingResponse.model_json_schema()
    properties = schema["properties"]

    assert set(EXPECTED_FACTORS) <= set(properties)
    assert "total" not in properties, "the total is computed in code, never by the model"


def test_every_factor_defaults_to_the_absent_sentinel() -> None:
    response = RankingResponse()

    for factor in EXPECTED_FACTORS:
        assert getattr(response, factor) == -1.0
    assert present_factors({f: getattr(response, f) for f in EXPECTED_FACTORS}) == ()
