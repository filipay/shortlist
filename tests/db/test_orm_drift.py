"""ORM-vs-migrated-schema drift guard (migration 0002 and everything before it).

`tests/db/test_migration_contract.py` deliberately reads the **migrated database**
through `PRAGMA`/`sqlite_master` and never the ORM metadata, so a model/DDL
divergence can pass the contract and still ship as an application bug. This guard
closes that gap in the opposite direction: it compares `Base.metadata` against the
schema `alembic upgrade head` actually produced.

Only **column names** are compared — SQLite's type affinity and Alembic's batch
recreation legitimately differ in spelling, so comparing types would be a false
alarm. Every application table is expected in both directions: an ORM-only table
(a model with no migration) and a DB-only table (a migration with no model) are
both drift.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import app.db.models  # noqa: F401  (importing registers every table on Base.metadata)
from app.db.base import Base

#: The objects migration 0002 adds. Asserted explicitly so a metadata-loading
#: mistake cannot make the comparison vacuous.
PHASE_2_TABLES = frozenset(
    {"filter_rules", "queue_state", "listing_dupes", "listing_exclusions", "runs"}
)

#: migration 0001 has 16 application tables and 0002 adds two more. A floor below
#: the real count still catches "metadata loaded nothing" without pinning the
#: exact inventory (which would make every future migration edit this file).
MIN_TABLE_COUNT = 15


def _db_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _db_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    # PRAGMA does not accept bound parameters; the table name comes from our own
    # `sqlite_master`, never from external input.
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _is_internal(table: str) -> bool:
    """Tables the ORM deliberately does not model."""
    return (
        table == "alembic_version"
        # The FTS5 virtual table and its shadow tables are raw DDL (0001).
        or table.startswith("listing_fts")
        or table.startswith("sqlite_")
        # APScheduler's job store (3.11.3, pinned) creates its own ``apscheduler_jobs``
        # table with ``CREATE TABLE ... IF NOT EXISTS`` the first time a scheduler
        # starts, outside Alembic. It is the LIBRARY's private schema and the library
        # owns its DDL, so it is exempt rather than mirrored: declaring it in our own
        # migration would hard-couple the repo to a third-party internal shape, and an
        # APScheduler upgrade that changed the columns would then need a hand-written
        # migration. The pin plus this exemption is the recorded mitigation (Pitfall 4).
        or table == "apscheduler_jobs"
    )


def test_orm_metadata_matches_migrated_schema(migrated_db: Path) -> None:
    connection = sqlite3.connect(migrated_db)
    connection.row_factory = sqlite3.Row
    try:
        discovered = _db_tables(connection)

        # Non-vacuity: the metadata really loaded, and the migrated DB really
        # carries the 0002 objects this guard exists to check.
        assert Base.metadata.tables, "no ORM tables are registered — the guard is vacuous"
        assert len(Base.metadata.tables) > MIN_TABLE_COUNT, (
            f"only {len(Base.metadata.tables)} ORM tables are registered"
        )
        assert len(discovered) > MIN_TABLE_COUNT, (
            f"only {len(discovered)} migrated tables were discovered"
        )
        assert PHASE_2_TABLES <= discovered, (
            f"the migrated schema is missing 0002 objects: {sorted(PHASE_2_TABLES - discovered)}"
        )

        # Both directions: no ORM-only table, and no unmirrored application table.
        application_tables = {name for name in discovered if not _is_internal(name)}
        assert application_tables == set(Base.metadata.tables), (
            "the ORM and the migrated schema disagree on the table set: "
            f"orm-only={sorted(set(Base.metadata.tables) - application_tables)} "
            f"db-only={sorted(application_tables - set(Base.metadata.tables))}"
        )

        # Per-table column-name equality.
        offenders: list[str] = []
        scanned = 0
        for table_name, table in Base.metadata.tables.items():
            scanned += 1
            orm_columns = {column.name for column in table.columns}
            db_columns = _db_columns(connection, table_name)
            if orm_columns != db_columns:
                offenders.append(
                    f"{table_name}: orm-only={sorted(orm_columns - db_columns)} "
                    f"db-only={sorted(db_columns - orm_columns)}"
                )

        assert scanned > 0, "no tables were compared — the guard is vacuous"
        assert offenders == [], (
            "the ORM mirror has drifted from the migrated schema: " + "; ".join(offenders)
        )
    finally:
        connection.close()
