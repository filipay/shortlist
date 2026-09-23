"""G-05-3 / UI-01 — `QueuePage`'s derived page accessors are total.

The pager in `queue_list.html` renders `page.page_index`, `page.page_count`,
`page.prev_offset` and `page.has_prev` directly. Those four are pure derivations of
`offset`/`limit`/`total`, which `read_queue` always sets — but the template can be
rendered from a hand-constructed page too, and a divide-by-zero or a negative
`prev_offset` there would 500 the Core Value screen. This file pins the totality:
no exception, `page_count >= 1`, `prev_offset >= 0`, on every degenerate shape.

`tests/db/test_queue_state.py` (the file the 05-11 SUMMARY names as this evidence)
is the last-visit watermark suite and contains no `QueuePage` assertion at all.
"""

from __future__ import annotations

import pytest

from app.db.repositories.queue_repo import QueuePage, QueueQuery


def _page(*, total: int, offset: int, limit: int, has_more: bool = False) -> QueuePage:
    return QueuePage(
        rows=(),
        total=total,
        offset=offset,
        limit=limit,
        has_more=has_more,
        query=QueueQuery(),
    )


def test_the_first_page_has_no_previous_and_reports_page_one() -> None:
    page = _page(total=5, offset=0, limit=2, has_more=True)

    assert page.has_prev is False
    assert page.prev_offset == 0
    assert page.page_index == 1
    assert page.page_count == 3


def test_a_middle_page_derives_its_position_and_a_non_negative_prev_offset() -> None:
    page = _page(total=5, offset=2, limit=2, has_more=True)

    assert page.has_prev is True
    assert page.prev_offset == 0, "offset 2 at page size 2 is the first page"
    assert page.page_index == 2
    assert page.page_count == 3


def test_the_last_page_derives_its_previous_offset() -> None:
    page = _page(total=5, offset=4, limit=2)

    assert page.has_prev is True
    assert page.prev_offset == 2
    assert page.page_index == 3
    assert page.page_count == 3


def test_an_empty_queue_is_still_one_page_never_zero() -> None:
    page = _page(total=0, offset=0, limit=25)

    assert page.page_count == 1, "the current page always exists"
    assert page.page_index == 1
    assert page.prev_offset == 0


def test_a_non_divisible_total_rounds_the_page_count_up() -> None:
    page = _page(total=6, offset=0, limit=4, has_more=True)

    assert page.page_count == 2, "ceil(6/4) is 2, not 1"


def test_an_offset_inside_a_page_never_yields_a_negative_prev_offset() -> None:
    page = _page(total=9, offset=1, limit=5, has_more=True)

    assert page.prev_offset == 0, "max(0, 1 - 5) is 0, never negative"
    assert page.page_index == 1, "offset 1 is still the first page at size 5"


def test_a_zero_page_size_does_not_divide_by_zero() -> None:
    """The `max(1, limit)` guard: a degenerate page must not raise, and must not 0 pages."""
    page = _page(total=7, offset=0, limit=0)

    assert page.page_count == 7, "each row is its own page at size 0, floored at 1"
    assert page.page_index == 1
    assert page.prev_offset == 0


def test_a_negative_page_size_is_also_guarded() -> None:
    page = _page(total=3, offset=0, limit=-4)

    assert page.page_count >= 1
    assert page.prev_offset >= 0


@pytest.mark.parametrize(
    ("total", "offset", "limit"),
    [(0, 0, 0), (1, 0, 0), (0, 5, 2), (3, 1, -1), (10, 10, 3), (2, 7, 5)],
)
def test_the_accessors_never_raise_and_stay_in_range(
    total: int, offset: int, limit: int
) -> None:
    page = _page(total=total, offset=offset, limit=limit)

    assert page.page_count >= 1
    assert page.page_index >= 1
    assert page.prev_offset >= 0
