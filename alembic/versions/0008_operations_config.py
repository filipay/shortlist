"""operations_config — the singleton operations document (D-153 / D-168)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14

The daily schedule (D-153) and the per-category retention thresholds (D-168) are
global configuration with no home in the existing schema: ``searches.schedule_cron``
is per-search (D-151) and nothing has ever written it. This revision adds one
single-purpose table rather than a generic key-value store, because nothing else
needs one yet.

Purely additive: one new table, no column dropped, renamed or made NOT NULL, and
no existing row rewritten. In particular it does **not** touch ``runs`` — widening
``runs.status`` for a "skipped" value would need a batch recreation of that table,
which is the exact hazard ``test_upgrade_populated_0001_to_head`` guards against.
``alembic downgrade 0007`` drops exactly this table and leaves every other table
intact.

Two deliberate choices:

* **The table is not seeded.** The repository falls back to its code-level
  ``DEFAULT_SCHEDULE`` when the row is absent, and a migration must not depend on
  application code — so this revision imports no application module and inserts no
  row.
* **``id`` is pinned to 1** by the explicitly named ``ck_operations_config_singleton``.
  An unnamed CHECK would be silently dropped when a later revision recreates the
  table (the repo convention stated in ``app/db/models.py``).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operations_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("schedule_json", sa.JSON, nullable=False),
        sa.Column("retention_json", sa.JSON, nullable=False),
        sa.Column("last_schedule_skip_json", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_operations_config_singleton"),
    )


def downgrade() -> None:
    # Symmetric: drop exactly the one table this revision added.
    op.drop_table("operations_config")
