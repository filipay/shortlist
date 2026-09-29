"""The description-derived years-of-experience signal (deterministic, no LLM).

A listing's own description often names a years floor that the ranker otherwise has
no explicit sight of. These helpers surface it as a soft ranking hint only: the
leading number of a range is the floor, a preference-qualified figure is not a
requirement, and an absent figure is never read as "0 required".

The extraction is pure `re` — no I/O, no classifier, no new dependency — so the
matched fragment stays traceable to the description text.
"""

from __future__ import annotations

import pytest

from app.domain.listing import (
    required_experience_fragment,
    required_experience_years,
)

# --- the positive path ---------------------------------------------------------


@pytest.mark.parametrize(
    "description,expected",
    [
        ("3-5 years of experience", 3),
        ("3+ years of experience", 3),
        ("at least 5 years experience", 5),
        ("minimum of 2 years in Python", 2),
        ("5+ years required", 5),
        ("10 years of experience", 10),
    ],
)
def test_a_stated_floor_is_read_from_the_description(description: str, expected: int) -> None:
    assert required_experience_years(description) == expected


@pytest.mark.parametrize("description", [None, "", "Build the thing."])
def test_no_figure_is_no_signal(description: str | None) -> None:
    assert required_experience_years(description) is None


def test_the_fragment_is_the_exact_matched_substring() -> None:
    description = "3-5 years of experience"

    fragment = required_experience_fragment(description)

    assert fragment, "a stated floor must quote the listing's own words"
    assert fragment in description
