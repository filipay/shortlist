"""screening_drafts + apply_config, and the application_events append-only triggers.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30

Two new tables plus two triggers on the **existing** ``application_events`` table:

* ``screening_drafts`` — a drafted screening answer, one row per question, per
  listing (D-124/D-126). It is a child of ``listings`` and is regenerable, so
  ``app/api/settings.py`` deletes it in ``RESET_DELETE_ORDER`` (before its parent).
* ``apply_config`` — the single-row user-editable screening-question document
  (D-124), mirroring ``ranking_config``'s singleton shape. It is user config, so
  ``app/api/settings.py`` keeps it in ``RESET_KEPT_TABLES``.

The triggers mirror ``listing_events``' append-only contract verbatim in shape
(migration 0001): current state lives on the ``applications`` row, history in
``application_events``. ``op.execute`` SUFFICES for both — ``CREATE TRIGGER`` is
raw DDL that does not recreate the target table, so no ``batch_alter_table`` is
required. There is deliberately NO new CHECK on ``to_status``/``from_status``:
adding a CHECK to an existing SQLite table forces a full table recreation of an FK
child, the hazard ``test_upgrade_populated_0001_to_head`` guards, and the status
vocabulary is validated in the repository against ``APPLICATION_STATUSES``.

Reset interaction: ``app/api/settings.py`` keeps ``applications`` in
``RESET_BLOCKING_TABLES``, so a guarded reset refuses while it holds any row. Since
``application_events.application_id`` is NOT NULL with an FK to ``applications``, an
event row cannot exist without an application row — a reset that proceeds has zero
events to delete and never needs to suspend these triggers. If ``applications`` is
ever moved into ``RESET_DELETE_ORDER``, ``_suspend_append_only_trigger`` must be
extended to drop/re-create ``application_events_no_delete`` and a re-arm test added.

Purely additive: two new tables and two triggers, no column dropped, renamed or
made NOT NULL, and no existing row rewritten. ``alembic downgrade 0005`` drops
exactly these objects.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_drafts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("answer_text", sa.Text),
        sa.Column("evidence_json", sa.JSON),
        sa.Column("unsupported", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "apply_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("questions_json", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_apply_config_singleton"),
    )

    # The append-only contract for `application_events` (mirrors 0001's
    # `listing_events` triggers). `op.execute` is sufficient: CREATE TRIGGER does
    # not recreate the target table.
    op.execute(
        "CREATE TRIGGER application_events_no_update BEFORE UPDATE ON application_events "
        "BEGIN SELECT RAISE(ABORT, 'application_events is append-only'); END;"
    )
    op.execute(
        "CREATE TRIGGER application_events_no_delete BEFORE DELETE ON application_events "
        "BEGIN SELECT RAISE(ABORT, 'application_events is append-only'); END;"
    )


def downgrade() -> None:
    # Symmetric: drop the triggers first, then exactly the two tables added here.
    op.execute("DROP TRIGGER IF EXISTS application_events_no_delete")
    op.execute("DROP TRIGGER IF EXISTS application_events_no_update")
    op.drop_table("apply_config")
    op.drop_table("screening_drafts")
