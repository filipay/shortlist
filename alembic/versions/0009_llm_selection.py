"""Global exact LLM selection and nullable generation provenance.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("operations_config") as batch:
        batch.add_column(sa.Column("llm_provider_id", sa.String(512), nullable=True))
        batch.add_column(sa.Column("llm_model_id", sa.String(512), nullable=True))
        batch.create_check_constraint(
            "ck_operations_config_llm_selection",
            "(llm_provider_id IS NULL AND llm_model_id IS NULL) OR "
            "(llm_provider_id IS NOT NULL AND llm_model_id IS NOT NULL "
            "AND length(trim(llm_provider_id)) > 0 AND length(trim(llm_model_id)) > 0)",
        )
    op.add_column("cv_drafts", sa.Column("requested_model", sa.String(512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cv_drafts") as batch:
        batch.drop_column("requested_model")
    with op.batch_alter_table("operations_config") as batch:
        batch.drop_constraint("ck_operations_config_llm_selection", type_="check")
        batch.drop_column("llm_model_id")
        batch.drop_column("llm_provider_id")
