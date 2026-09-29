"""The pinned JobSpy column contract signal S6 depends on.

Source of truth: `jobspy/util.py` `desired_order`. If JobSpy renames or removes a
column, this test (and the source fixtures below) must fail loudly — S6 detects
drift by comparing the returned frame columns against `DESIRED_ORDER`.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sources._jobspy_mapping import DESIRED_ORDER, map_jobspy_row

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "listings"

#: Copied verbatim from `jobspy/util.py` `desired_order`. Do not edit to "fix" a
#: failing test without first checking the installed library.
EXPECTED_DESIRED_ORDER = (
    "id",
    "site",
    "job_url",
    "job_url_direct",
    "title",
    "company",
    "location",
    "date_posted",
    "job_type",
    "salary_source",
    "interval",
    "min_amount",
    "max_amount",
    "currency",
    "is_remote",
    "job_level",
    "job_function",
    "listing_type",
    "emails",
    "description",
    "company_industry",
    "company_url",
    "company_logo",
    "company_url_direct",
    "company_addresses",
    "company_num_employees",
    "company_revenue",
    "company_description",
    # naukri-specific tail
    "skills",
    "experience_range",
    "company_rating",
    "company_reviews_count",
    "vacancy_count",
    "work_from_home_type",
)


def test_desired_order_is_the_exact_pinned_jobspy_column_contract() -> None:
    assert DESIRED_ORDER == EXPECTED_DESIRED_ORDER


def test_source_fixtures_carry_the_full_pinned_column_set() -> None:
    """The fixtures must mirror the real flattened frame, not a convenient subset."""
    for path in sorted(FIXTURES.glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        assert rows, f"{path.name} is empty"
        for row in rows:
            assert set(row) == set(DESIRED_ORDER), (
                f"{path.name} does not carry the full desired_order column set"
            )


def test_job_level_maps_to_the_small_seniority_vocabulary() -> None:
    """The board's own `job_level` is read into the core `seniority` field."""
    assert map_jobspy_row({"job_level": "Entry level"}, source="indeed").seniority == "junior"
    assert map_jobspy_row({"job_level": "Internship"}, source="linkedin").seniority == "junior"
    mid_senior = map_jobspy_row({"job_level": "Mid-Senior level"}, source="linkedin")
    assert mid_senior.seniority == "senior"
    assert map_jobspy_row({"job_level": "Director"}, source="linkedin").seniority == "senior"
    assert map_jobspy_row({"job_level": "Associate"}, source="linkedin").seniority is None
    unknown = map_jobspy_row({"job_level": "Something unrecognised"}, source="linkedin")
    assert unknown.seniority is None
    assert map_jobspy_row({}, source="linkedin").seniority is None
