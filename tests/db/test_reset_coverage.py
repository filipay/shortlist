"""A future table that references `listings` must force a reset decision.

The reset deletes a fixed list of tables and refuses while another list holds rows. A
new child table would otherwise be silently orphaned (or silently block) — so this test
enumerates every child of `listings` from the live metadata and requires each to be in
exactly one of the two lists.
"""

from __future__ import annotations

from app.api.settings import RESET_BLOCKING_TABLES, RESET_DELETE_ORDER
from app.db.models import Base


def _children_of_listings() -> set[str]:
    children: set[str] = set()
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name == "listings":
                children.add(table.name)
    return children


def test_every_listing_child_is_deleted_or_declared() -> None:
    children = _children_of_listings()

    assert children, "the metadata has no children of `listings` — the scan is vacuous"
    undecided = children - set(RESET_DELETE_ORDER) - set(RESET_BLOCKING_TABLES)
    assert undecided == set(), (
        f"{sorted(undecided)} reference `listings` but the reset neither deletes them "
        "nor refuses while they hold rows; decide and add each to RESET_DELETE_ORDER "
        "or RESET_BLOCKING_TABLES"
    )


def test_the_two_lists_do_not_overlap() -> None:
    assert set(RESET_DELETE_ORDER) & set(RESET_BLOCKING_TABLES) == set()


def test_every_named_table_exists() -> None:
    for name in (*RESET_DELETE_ORDER, *RESET_BLOCKING_TABLES):
        assert name in Base.metadata.tables, name
