"""Add persistent translator name aliases.

Revision ID: 20260731_0006
Revises: 20260730_0005
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "20260731_0006"
down_revision = "20260730_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "translator_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("translator_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["translator_id"],
            ["translators.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "normalized_alias",
            name="uq_translator_aliases_normalized_alias",
        ),
    )
    op.create_index(
        "ix_translator_aliases_translator_id",
        "translator_aliases",
        ["translator_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_translator_aliases_translator_id",
        table_name="translator_aliases",
    )
    op.drop_table("translator_aliases")
