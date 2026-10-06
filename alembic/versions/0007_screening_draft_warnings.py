"""screening_drafts.warnings_json + band — the checker's specific findings survive

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06

G-07-3: ``ground_screening_answers`` already computes, per answer, ``warnings`` (one
human sentence per finding, each naming the offending evidence id or novel digit
token) and an advisory ``band``. The persist path kept only the ``unsupported``
boolean plus the already-grounded ``evidence_json`` — and the offender was
deliberately dropped from that grounded set, so once the verdict was discarded the
finding was gone and the renderer could only emit a fixed generic caution.

Two nullable columns, purely additive: no backfill, no CHECK, no table recreation —
a nullable ``op.add_column`` is a true in-place ALTER on SQLite (migration 0003's
precedent).

* ``warnings_json`` — the checker's human sentences, each naming its offender. A JSON
  column, allow-listed in ``tests/db/test_no_pii_columns.py``: it carries fact ids and
  digit tokens, never recruiter PII.
* ``band`` — the advisory ``GroundingBand`` label (``grounded`` / ``borderline`` /
  ``ungrounded``). Advisory by construction; it never flips ``unsupported``.

NULL on either column means "no specifics recorded" (a legacy or directly-seeded
row); the renderer treats that as the generic-caution fallback.

``alembic downgrade 0006`` drops exactly the two columns this revision added.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("screening_drafts", sa.Column("warnings_json", sa.JSON))
    op.add_column("screening_drafts", sa.Column("band", sa.String(16)))


def downgrade() -> None:
    # Symmetric: drop exactly the two columns this revision added.
    op.drop_column("screening_drafts", "band")
    op.drop_column("screening_drafts", "warnings_json")
