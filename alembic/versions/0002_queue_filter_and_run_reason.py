"""queue filter rules, the last-visit watermark and the run-reason columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16

The only schema change in Phase 2, and it is **purely additive** (T-02-01): no
column is dropped, renamed or made NOT NULL, and no existing row is rewritten.
Migration 0001 deliberately shipped every other Phase-2 table (D-47); this one
adds exactly the four things it omitted:

1. ``filter_rules`` — typed, ordered, per-search filter rows (D-34 / CRIT-01 /
   FILT-04). ``kind`` carries the explicitly named ``ck_filter_rules_kind`` so
   an unknown rule vocabulary cannot be persisted.
2. ``queue_state`` — the single-row last-visit watermark (D-39 / QUEUE-07).
   ``last_queue_view_at`` is NULLABLE: ``NULL`` means "never viewed", so every
   listing starts out new.
3. ``runs.reason`` / ``reason_counts_json`` / ``stage_log_json`` /
   ``criteria_snapshot_json`` — the persisted empty-reason enum, its counts, the
   raw stage log, and the criteria snapshot that makes a past run reproducible
   (D-33 / D-44 / RUN-03). ``reason`` is NULLABLE so ``NULL`` legitimately means
   "this run produced a non-empty queue".
4. ``listing_exclusions.criteria_version`` (D-33 / CRIT-02) and the two
   ``listing_dupes`` indexes: a UNIQUE ``(listing_id, dup_listing_id)`` that
   stops a same-orientation re-insert, and the ``dup_listing_id`` index that
   makes the either-orientation negative-memory lookup (plan 02-04) index-usable.

SQLite cannot ALTER in a CHECK constraint, so the named ``ck_runs_reason`` is
added through the batch/table-recreation path. **Every CHECK is named
explicitly** — an unnamed CHECK is silently dropped by a later batch
recreation (the repo convention stated in ``app/db/models.py``).

The append-only ``listing_events`` triggers and the FTS5 virtual table with its
triggers are deliberately untouched: they are correct, and recreating the search
index risks divergence. The searchable FTS column set is pinned to ``(title,
company_norm, description)``, so no FTS change is needed.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

#: The typed rule vocabulary (D-34). Kept as a literal list so the CHECK is
#: readable in the migrated DDL and asserted by the migration-contract test.
FILTER_RULE_KINDS = (
    "'salary_floor','exclude_keyword','location','remote','seniority','company_blocklist'"
)

#: The run-reason enum (D-44). ``NULL`` means "the queue was not empty".
RUN_REASONS = (
    "'no_sources_enabled','all_sources_failed','zero_fetched','all_filtered','nothing_new','mixed'"
)


def upgrade() -> None:
    # -- 1. filter_rules (D-34 / CRIT-01 / FILT-04) ------------------------
    op.create_table(
        "filter_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("search_id", sa.Integer, sa.ForeignKey("searches.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("params_json", sa.JSON),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(f"kind IN ({FILTER_RULE_KINDS})", name="ck_filter_rules_kind"),
    )
    op.create_index(
        "ix_filter_rules_search_position", "filter_rules", ["search_id", "position"]
    )

    # -- 2. queue_state (D-39 / QUEUE-07) ----------------------------------
    # One row, no JSON column. `last_queue_view_at` is nullable on purpose.
    op.create_table(
        "queue_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("last_queue_view_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # -- 3. runs + listing_exclusions columns (D-33 / D-44 / RUN-03) -------
    # `op.add_column` with a nullable column is a true in-place ALTER on SQLite.
    op.add_column("runs", sa.Column("reason", sa.String(32)))
    op.add_column("runs", sa.Column("reason_counts_json", sa.JSON))
    op.add_column("runs", sa.Column("stage_log_json", sa.JSON))
    op.add_column("runs", sa.Column("criteria_snapshot_json", sa.JSON))
    op.add_column("listing_exclusions", sa.Column("criteria_version", sa.Integer))

    # A CHECK on an existing table needs the batch path; the constraint is
    # created separately from the column because a CheckConstraint cannot be
    # appended with `op.add_column`.
    with op.batch_alter_table("runs") as batch_op:
        batch_op.create_check_constraint(
            "ck_runs_reason", f"reason IS NULL OR reason IN ({RUN_REASONS})"
        )

    # -- 4. listing_dupes indexes (QUEUE-03/QUEUE-04 negative memory) ------
    op.create_index(
        "uq_listing_dupes_pair",
        "listing_dupes",
        ["listing_id", "dup_listing_id"],
        unique=True,
    )
    op.create_index(
        "ix_listing_dupes_dup_listing_id", "listing_dupes", ["dup_listing_id"]
    )


def downgrade() -> None:
    # Drop in reverse, deepest-first. This exists only so Alembic's tooling
    # stays coherent in a throwaway database (0001 is the one-way door).
    op.drop_index("ix_listing_dupes_dup_listing_id", table_name="listing_dupes")
    op.drop_index("uq_listing_dupes_pair", table_name="listing_dupes")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_constraint("ck_runs_reason", type_="check")
    op.drop_column("runs", "criteria_snapshot_json")
    op.drop_column("runs", "stage_log_json")
    op.drop_column("runs", "reason_counts_json")
    op.drop_column("runs", "reason")

    op.drop_column("listing_exclusions", "criteria_version")

    op.drop_table("queue_state")
    op.drop_index("ix_filter_rules_search_position", table_name="filter_rules")
    op.drop_table("filter_rules")
