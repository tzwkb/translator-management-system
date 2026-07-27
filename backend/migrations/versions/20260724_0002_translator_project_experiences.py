"""Add translator profile fields and project experiences.

Revision ID: 20260724_0002
Revises: 20260717_0001
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260724_0002"
down_revision = "20260717_0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("translators") as batch_op:
        batch_op.add_column(sa.Column("gender", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("entity_type", sa.String(20), nullable=True))

    op.create_table(
        "translator_project_experiences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "translator_id",
            sa.Integer(),
            sa.ForeignKey("translators.id"),
            nullable=False,
        ),
        sa.Column("cooperation_source", sa.String(20), nullable=False),
        sa.Column("project_status", sa.String(20), nullable=False),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("external_company", sa.String(200), nullable=True),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("source_lang", sa.String(20), nullable=True),
        sa.Column("target_lang", sa.String(20), nullable=True),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("remaining_volume", sa.Numeric(14, 2), nullable=True),
        sa.Column("deadline", sa.String(20), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_translator_project_experiences_translator_id",
        "translator_project_experiences",
        ["translator_id"],
    )
    op.create_index(
        "ix_translator_project_experiences_cooperation_source",
        "translator_project_experiences",
        ["cooperation_source"],
    )
    op.create_index(
        "ix_translator_project_experiences_project_status",
        "translator_project_experiences",
        ["project_status"],
    )


def downgrade():
    op.drop_table("translator_project_experiences")
    with op.batch_alter_table("translators") as batch_op:
        batch_op.drop_column("entity_type")
        batch_op.drop_column("gender")
