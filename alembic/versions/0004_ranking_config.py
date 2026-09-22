"""ranking_config — the single-row global weights document (D-99 / D-100)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

The live six-number weights document had no home in the existing schema:
``searches.criteria_json`` is per-search, which D-99 forbids, and
``scores.weights_json`` is a per-score audit snapshot of what was in force at
scoring time (D-100), not the live setting. This revision adds one
single-purpose table rather than a generic key-value store, because nothing else
needs one yet.

Purely additive: one new table, no column dropped, renamed or made NOT NULL, and
no existing row rewritten. ``alembic downgrade 0003`` drops exactly this table and
leaves every other table intact.

Two deliberate choices:

* **The table is not seeded.** The repository falls back to
  ``app.domain.rubric.DEFAULT_WEIGHTS`` when the row is absent, and a migration
  must not depend on application code — so this revision imports no application
  module and inserts no row.
* **``id`` is pinned to 1** by the explicitly named ``ck_ranking_config_singleton``.
  An unnamed CHECK would be silently dropped by a later ``batch_alter_table``
  table recreation (the repo convention stated in ``app/db/models.py``).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ranking_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("weights_json", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_ranking_config_singleton"),
    )


def downgrade() -> None:
    # Symmetric: drop exactly the one table this revision added.
    op.drop_table("ranking_config")
