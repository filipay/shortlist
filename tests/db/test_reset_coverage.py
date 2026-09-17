"""A future child of a table the reset empties must force a reset decision.

The reset deletes a fixed list of tables and refuses while another list holds rows. The
reset does not only empty `listings`: it empties `runs` too, so every child of either
parent has to be accounted for. A new child table would otherwise be silently orphaned
(or silently block) — so this test enumerates the children from the live metadata and
requires each to land in exactly one of the two lists (for `listings`) or in the delete
order (for `runs`, which is history and is always deleted, never a reason to refuse).
"""

from __future__ import annotations

from app.api.settings import RESET_BLOCKING_TABLES, RESET_DELETE_ORDER
from app.db.models import Base


def _children_of(parent: str) -> set[str]:
    """Every table with a foreign key to `parent`, enumerated from the live metadata."""
    children: set[str] = set()
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name == parent:
                children.add(table.name)
    return children


def test_every_listing_child_is_deleted_or_declared() -> None:
    children = _children_of("listings")

    assert children, "the metadata has no children of `listings` — the scan is vacuous"
    undecided = children - set(RESET_DELETE_ORDER) - set(RESET_BLOCKING_TABLES)
    assert undecided == set(), (
        f"{sorted(undecided)} reference `listings` but the reset neither deletes them "
        "nor refuses while they hold rows; decide and add each to RESET_DELETE_ORDER "
        "or RESET_BLOCKING_TABLES"
    )


def test_every_run_child_is_deleted() -> None:
    """`runs` is emptied too, so every child of it must be in the delete order.

    Unlike `listings`, a run child has no blocking list: a row referencing a run is run
    history, not tracked work, so the only correct decision is to delete it (before its
    parent). A future table referencing `runs.id` that is not listed here fails closed —
    otherwise it would only surface as a runtime FK failure during a real reset.
    """
    children = _children_of("runs")

    assert children, "the metadata has no children of `runs` — the scan is vacuous"
    orphans = children - set(RESET_DELETE_ORDER)
    assert orphans == set(), (
        f"{sorted(orphans)} reference `runs` but the reset does not delete them; add "
        "each to RESET_DELETE_ORDER before `runs`"
    )


def test_the_two_lists_do_not_overlap() -> None:
    assert set(RESET_DELETE_ORDER) & set(RESET_BLOCKING_TABLES) == set()


def test_every_named_table_exists() -> None:
    for name in (*RESET_DELETE_ORDER, *RESET_BLOCKING_TABLES):
        assert name in Base.metadata.tables, name


def test_delete_order_puts_every_parent_after_its_child() -> None:
    """With `foreign_keys=ON`, a parent deleted before its child raises at runtime."""
    order = {name: index for index, name in enumerate(RESET_DELETE_ORDER)}
    violations: list[str] = []
    for child in RESET_DELETE_ORDER:
        for foreign_key in Base.metadata.tables[child].foreign_keys:
            parent = foreign_key.column.table.name
            if parent in order and order[parent] < order[child]:
                violations.append(f"{child} -> {parent}")
    assert violations == [], (
        f"these children are deleted after their parent: {sorted(violations)}; reorder "
        "RESET_DELETE_ORDER so every child precedes its parent"
    )
