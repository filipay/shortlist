"""llm_calls.server_version — the opencode version each call was made against

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17

D-12 / PITFALLS M9: `llm_calls` already records `provider` / `model` / `agent` /
`attempts` / `latency_ms`, but nothing says WHICH opencode server version produced
a call, so a model/version regression cannot be traced after the fact. Every other
candidate column already has a distinct meaning another surface relies on:
`backend` is `String(16)` and means "which transport"; `provider` is the provider
id; `error` is the failure cause and is NULL on a *successful* row, where the
version is most needed. Overloading any of them would corrupt the field the
Phase-5 operator reads.

Purely additive: one nullable column, no backfill, no data rewrite, no existing
column touched and no CHECK changed. A nullable `op.add_column` is a true in-place
ALTER on SQLite — migration 0002's `runs` columns are the exact precedent.

`llm_calls` gains **no JSON column**, so `tests/db/test_no_pii_columns.py`'s
`"llm_calls": frozenset()` allow-list stays unchanged: a bounded `VARCHAR(32)`
cannot carry a raw provider payload or a raw model response body.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable => a true in-place ALTER on SQLite (same as 0002's runs columns).
    op.add_column("llm_calls", sa.Column("server_version", sa.String(32)))


def downgrade() -> None:
    # Symmetric: drop exactly the one column this revision added.
    op.drop_column("llm_calls", "server_version")
