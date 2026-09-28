"""cv_drafts — the one live generated draft per listing (D-108 superseded)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28

``POST .../cv/generate`` deliberately persisted nothing (D-108): it returned an HTML
fragment whose hidden ``patch_json`` field carried the patch, and page state came only
from compiled ``cv_artifacts`` rows — so a reload or a navigation away lost the
generated CV. The explicit user requirement is now the opposite: the generated CV is
kept per job and removed only by an explicit delete.

A dedicated table rather than a ``'draft'`` status on ``cv_artifacts``:
``cv_artifacts.compile_status`` carries a three-value CHECK (``ok``/``failed``/
``blocked``) mirrored in migration 0001, and its reads filter on ``listing_id`` alone,
so a draft there would pollute compiled history and the page's latest-artifact state.
This revision adds the smallest table that answers the requirement instead of widening
that CHECK.

Purely additive: one new table, no column dropped, renamed or made NOT NULL, and no
existing row rewritten. ``alembic downgrade 0004`` drops exactly this table and leaves
every other table intact.

Two deliberate choices:

* **One live draft per listing** is enforced by the explicitly named
  ``uq_cv_drafts_listing`` unique constraint. An unnamed constraint would be silently
  dropped by a later ``batch_alter_table`` table recreation (the repo convention in
  ``app/db/models.py``).
* **Only ``patch_json`` is stored as a JSON blob**, and it carries the typed
  :class:`~app.domain.cv.TailoringPatch` (fact IDs, weights and reasons — never free
  text and never listing content), so the no-PII JSON allow-list gains one accountable
  entry rather than a new place for PII to land.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cv_drafts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("base_cv_version_id", sa.Integer, sa.ForeignKey("cv_versions.id")),
        sa.Column("patch_json", sa.JSON, nullable=False),
        sa.Column("fact_store_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("listing_id", name="uq_cv_drafts_listing"),
    )


def downgrade() -> None:
    # Symmetric: drop exactly the one table this revision added.
    op.drop_table("cv_drafts")
