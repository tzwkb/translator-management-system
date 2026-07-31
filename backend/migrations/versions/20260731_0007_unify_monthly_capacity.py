"""Unify capacity around project-word monthly allocation.

Revision ID: 20260731_0007
Revises: 20260731_0006
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "20260731_0007"
down_revision = "20260731_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "capacity_month_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("translator_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["translator_id"], ["translators.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "translator_id",
            "month",
            name="uq_capacity_month_overrides_translator_month",
        ),
    )
    op.create_index(
        "ix_capacity_month_overrides_translator_id",
        "capacity_month_overrides",
        ["translator_id"],
        unique=False,
    )
    op.create_index(
        "ix_capacity_month_overrides_month",
        "capacity_month_overrides",
        ["month"],
        unique=False,
    )
    op.execute("""
        INSERT INTO capacity_month_overrides
            (translator_id, month, status, reason, updated_by, updated_at)
        SELECT id, strftime('%Y-%m', 'now', 'localtime'), availability,
               '由旧全局人工档期迁移', 'schema-migration', CURRENT_TIMESTAMP
        FROM translators
        WHERE availability IN ('空闲', '健康', '饱和', '警告')
    """)
    op.drop_index(
        "ix_capacity_allocations_translator_id",
        table_name="capacity_allocations",
    )
    op.drop_table("capacity_allocations")
    with op.batch_alter_table("translators") as batch_op:
        batch_op.drop_column("availability")
        batch_op.drop_column("weekend_off")


def downgrade():
    with op.batch_alter_table("translators") as batch_op:
        batch_op.add_column(sa.Column("availability", sa.String(length=50)))
        batch_op.add_column(sa.Column("weekend_off", sa.Boolean()))
    op.execute("""
        UPDATE translators
        SET availability = (
            SELECT status
            FROM capacity_month_overrides
            WHERE capacity_month_overrides.translator_id = translators.id
            ORDER BY month DESC, id DESC
            LIMIT 1
        )
    """)
    op.create_table(
        "capacity_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("translator_id", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("week_no", sa.Integer(), nullable=False),
        sa.Column("project", sa.String(length=200), nullable=True),
        sa.Column("occupancy_pct", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["translator_id"], ["translators.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_capacity_allocations_translator_id",
        "capacity_allocations",
        ["translator_id"],
        unique=False,
    )
    op.drop_index(
        "ix_capacity_month_overrides_month",
        table_name="capacity_month_overrides",
    )
    op.drop_index(
        "ix_capacity_month_overrides_translator_id",
        table_name="capacity_month_overrides",
    )
    op.drop_table("capacity_month_overrides")
