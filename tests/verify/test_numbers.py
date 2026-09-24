"""D-113 / A2 / A3 — the metric tokeniser and the region segmentation.

Every documented edge case from the `must_haves` truth is pinned here: an affix, a
range, a percent, a thousands separator, a decimal, a magnitude suffix, a date
core, and a page-number line. The region cases pin both a found org and an absent
one, so the "an absent org is an entity failure, not a metric failure" rule is
enforced rather than assumed.
"""

from __future__ import annotations

from app.domain.cv import (
    Bullet,
    RenderPlan,
    RenderedEntry,
    RenderedSection,
    Skill,
)
from app.verify.numbers import (
    date_like_cores_for_entry,
    digit_cores,
    is_page_number_line,
    region_token_report,
)
from tests.verify.fixtures import build_fixture

# --- digit cores ---------------------------------------------------------------


def test_the_acceptance_literal_yields_the_documented_cores() -> None:
    text = "5+ and 5-10 and 40% and 1,200 and 0.5 and 50k"

    assert digit_cores(text) == ["5", "5", "10", "40", "1200", "0.5", "50"]


def test_a_plus_affix_does_not_create_a_new_token() -> None:
    assert digit_cores("5+") == ["5"]


def test_a_range_yields_two_cores() -> None:
    assert digit_cores("5-10") == ["5", "10"]


def test_a_percent_affix_does_not_create_a_new_token() -> None:
    assert digit_cores("40%") == ["40"]


def test_a_thousands_separator_is_removed() -> None:
    assert digit_cores("1,200") == ["1200"]


def test_a_decimal_point_is_preserved() -> None:
    assert digit_cores("0.5") == ["0.5"]


def test_a_decimal_comma_is_normalised_to_a_point() -> None:
    assert digit_cores("0,5") == ["0.5"]


def test_a_magnitude_suffix_is_dropped() -> None:
    assert digit_cores("50k") == ["50"]


def test_an_ordinal_yields_its_integer_core() -> None:
    assert digit_cores("3rd") == ["3"]


def test_the_tokeniser_is_total() -> None:
    assert digit_cores("") == []


# --- date-like cores -----------------------------------------------------------


def test_date_like_cores_are_the_year_and_month_cores() -> None:
    entry = build_fixture().plan.sections[0].entries[0]

    assert date_like_cores_for_entry(entry) == {"2021", "03", "2024", "09"}


# --- page-number lines ---------------------------------------------------------


def test_a_lone_integer_within_the_page_count_is_a_page_number() -> None:
    assert is_page_number_line("2", page_count=3) is True
    assert is_page_number_line("  1  ", page_count=3) is True


def test_zero_is_not_a_page_number() -> None:
    assert is_page_number_line("0", page_count=3) is False


def test_an_integer_above_the_page_count_is_not_a_page_number() -> None:
    assert is_page_number_line("4", page_count=3) is False
    assert is_page_number_line("12", page_count=3) is False


def test_a_prose_line_is_not_a_page_number() -> None:
    assert is_page_number_line("Experience", page_count=3) is False


# --- region segmentation -------------------------------------------------------


def test_the_region_carries_only_its_grounded_tokens() -> None:
    fixture = build_fixture()

    reports = region_token_report(fixture.plan, fixture.text, page_count=1)

    assert len(reports) == 1
    report = reports[0]
    assert report.entry_id == "exp/northwind-labs-2021"
    assert report.found is True
    # The date cores are excluded; only the two metric tokens survive.
    assert report.candidates == ["99", "40"]
    assert set(report.candidates) <= set(report.allowed)


def test_a_date_core_is_never_a_candidate() -> None:
    fixture = build_fixture()

    report = region_token_report(fixture.plan, fixture.text, page_count=1)[0]

    assert "2021" not in report.candidates
    assert "03" not in report.candidates


def test_a_page_number_line_is_never_a_candidate() -> None:
    fixture = build_fixture(extract_name="three_page_extract.txt", page_count=3)

    report = region_token_report(fixture.plan, fixture.text, page_count=3)[0]

    assert "1" not in report.candidates
    assert report.candidates == ["99", "40"]


def test_an_absent_org_is_reported_not_found() -> None:
    fixture = build_fixture(extract_name="missing_entity_extract.txt")

    report = region_token_report(fixture.plan, fixture.text, page_count=1)[0]

    assert report.found is False
    assert report.candidates == []


# --- GAP 1 / WR-03: region-local exclusion -------------------------------------


def test_a_foreign_date_core_is_not_excluded_in_another_region() -> None:
    """WR-03: entry B's year must NOT excuse that token inside entry A's region."""
    entry_a = RenderedEntry(
        id="exp/alpha-2019",
        org="Alpha Corp",
        title="Engineer",
        dates="2019-01 -- 2020-12",
        bullets=[Bullet(id="bul/alpha-2019/1", text="Launched the 2022 campaign")],
    )
    entry_b = RenderedEntry(
        id="exp/beta-2022",
        org="Beta Inc",
        title="Analyst",
        dates="2022-05 -- present",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry_a, entry_b],
            )
        ]
    )
    text = (
        "Alpha Corp --- Engineer\n"
        "2019-01 -- 2020-12\n"
        "Launched the 2022 campaign\n"
        "Beta Inc --- Analyst\n"
        "2022-05 -- present\n"
    )

    reports = region_token_report(plan, text, page_count=1)

    # The token is a candidate in A's region (A does not carry the year 2022) ...
    assert "2022" in reports[0].candidates
    # ... and B's own date still excuses it inside B's region.
    assert "2022" not in reports[1].candidates


def test_a_digit_in_a_skill_label_appearing_in_the_region_is_not_a_candidate() -> None:
    """CR-01: a digit-bearing skill label rendered in the region is grounded, not surplus."""
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme",
        title="Dev",
        dates="2020-01 -- 2021-01",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry],
                skills=[Skill(id="skill.aws", label="AWS S3", group="infrastructure")],
            )
        ]
    )
    text = (
        "Acme --- Dev\n"
        "2020-01 -- 2021-01\n"
        "Did things\n"
        "infrastructure AWS S3\n"
    )

    report = region_token_report(plan, text, page_count=1)[0]

    assert "3" not in report.candidates
    assert "3" in report.allowed


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
