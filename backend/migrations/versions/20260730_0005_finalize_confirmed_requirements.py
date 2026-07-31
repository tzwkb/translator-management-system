"""Finalize confirmed business rules.

Revision ID: 20260730_0005
Revises: 20260729_0004
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260730_0005"
down_revision = "20260729_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("translators") as batch_op:
        batch_op.add_column(sa.Column("manual_rating", sa.String(20)))
        batch_op.add_column(sa.Column("manual_rating_reason", sa.Text()))

    with op.batch_alter_table("quality_scores") as batch_op:
        batch_op.add_column(sa.Column("is_qualified", sa.Boolean()))
        batch_op.add_column(sa.Column("failure_reason", sa.Text()))

    op.drop_index("ux_payment_accounts_default", table_name="payment_accounts")
    with op.batch_alter_table("payment_accounts") as batch_op:
        batch_op.alter_column(
            "account_name",
            existing_type=sa.String(100),
            nullable=True,
        )

    op.execute("UPDATE payment_accounts SET is_default = 0")
    op.execute(
        "UPDATE translators SET availability = '健康' "
        "WHERE availability = '部分空闲'"
    )
    op.execute(
        "UPDATE translators SET availability = '饱和' "
        "WHERE availability = '满负荷'"
    )


def downgrade():
    op.execute(
        "UPDATE translators SET availability = '部分空闲' "
        "WHERE availability = '健康'"
    )
    op.execute(
        "UPDATE translators SET availability = '满负荷' "
        "WHERE availability IN ('饱和', '警告')"
    )
    op.execute(
        "UPDATE payment_accounts SET account_name = '' "
        "WHERE account_name IS NULL"
    )

    with op.batch_alter_table("payment_accounts") as batch_op:
        batch_op.alter_column(
            "account_name",
            existing_type=sa.String(100),
            nullable=False,
        )
    op.create_index(
        "ux_payment_accounts_default",
        "payment_accounts",
        ["translator_id"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    with op.batch_alter_table("quality_scores") as batch_op:
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("is_qualified")

    with op.batch_alter_table("translators") as batch_op:
        batch_op.drop_column("manual_rating_reason")
        batch_op.drop_column("manual_rating")
