"""SRC-09 / T-01-18 — a filter a board cannot honour is warned about, never dropped."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.sources.base import (
    CapabilityWarning,
    CompiledQuery,
    SearchQuery,
    SourceCapabilities,
    compile_query_for_source,
)

#: A board that can do nothing beyond a keyword search.
WEAK = SourceCapabilities(
    supports_salary=False,
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    supports_full_description_in_search=False,
    requires_second_pass_for_description=True,
    supports_offset_paging=True,
    max_results_per_query=None,
)

#: A board with everything switched on.
FULL = replace(
    WEAK,
    supports_salary=True,
    supports_salary_min_filter=True,
    supports_seniority=True,
)

#: LinkedIn's shape: no salary filter and the {hours_old, easy_apply} exclusivity.
EXCLUSIVE = replace(
    WEAK,
    exclusive_filter_groups=(frozenset({"hours_old", "easy_apply"}),),
)


def test_unsupported_salary_floor_is_dropped_and_warned() -> None:
    result = compile_query_for_source(
        SearchQuery(keywords="python", salary_floor=70000), WEAK, source="linkedin"
    )

    assert isinstance(result, CompiledQuery)
    assert result.query.salary_floor is None, "an unsupported filter must not be sent"
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert isinstance(warning, CapabilityWarning)
    assert warning.source == "linkedin"
    assert warning.filter_name == "salary_floor"
    assert "salary" in warning.reason


def test_unsupported_seniority_and_remote_are_dropped_and_warned() -> None:
    weak = replace(WEAK, supports_remote_flag=False)

    result = compile_query_for_source(
        SearchQuery(keywords="python", seniority=("senior",), remote_only=True),
        weak,
        source="board",
    )

    assert result.query.seniority == ()
    assert result.query.remote_only is None
    assert [w.filter_name for w in result.warnings] == ["remote_only", "seniority"]


def test_fully_supported_query_emits_no_warnings() -> None:
    result = compile_query_for_source(
        SearchQuery(keywords="python", salary_floor=70000, seniority=("senior",)),
        FULL,
        source="adzuna",
    )

    assert result.warnings == ()
    assert result.query.salary_floor == 70000
    assert result.query.seniority == ("senior",)


def test_exclusive_group_keeps_at_most_one_member_and_warns_the_other() -> None:
    result = compile_query_for_source(
        SearchQuery(keywords="python", hours_old=24, easy_apply=True),
        EXCLUSIVE,
        source="linkedin",
    )

    surviving = [
        name
        for name in ("hours_old", "easy_apply")
        if getattr(result.query, name) is not None
    ]
    assert len(surviving) <= 1, "the board silently honours only one of the pair"
    assert surviving == ["easy_apply"], "the alphabetically-first member is kept"
    assert [w.filter_name for w in result.warnings] == ["hours_old"]


def test_exclusive_group_is_a_no_op_when_only_one_member_is_requested() -> None:
    result = compile_query_for_source(
        SearchQuery(keywords="python", hours_old=24), EXCLUSIVE, source="linkedin"
    )

    assert result.query.hours_old == 24
    assert result.warnings == ()


def test_warnings_are_deterministically_ordered() -> None:
    weak = replace(WEAK, supports_remote_flag=False)
    query = SearchQuery(
        keywords="python", salary_floor=1, seniority=("senior",), remote_only=True
    )

    first = compile_query_for_source(query, weak, source="board")
    second = compile_query_for_source(query, weak, source="board")

    assert first.warnings == second.warnings
    names = [warning.filter_name for warning in first.warnings]
    assert names == sorted(names), "identical inputs must produce identical records"
    assert names == ["remote_only", "salary_floor", "seniority"]


def test_two_sources_compile_against_their_own_capabilities() -> None:
    query = SearchQuery(keywords="platform engineer", salary_floor=70000)

    capable = compile_query_for_source(query, FULL, source="adzuna")
    incapable = compile_query_for_source(query, WEAK, source="linkedin")

    assert capable.query.salary_floor == 70000, "pushed to the API — saves quota"
    assert capable.warnings == ()
    assert incapable.query.salary_floor is None, "applied locally instead, not silently"
    assert [w.filter_name for w in incapable.warnings] == ["salary_floor"]


def test_backwards_compatible_text_view_still_works() -> None:
    from app.sources.base import capability_warnings

    messages = capability_warnings(WEAK, SearchQuery(keywords="x", salary_floor=1))

    assert messages and "salary_floor" in messages[0]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
