"""Add persistent PO import batch and row logs.

Revision ID: 20260805_0008
Revises: 20260731_0007
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0008"
down_revision = "20260731_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "po_import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=50), nullable=False),
        sa.Column("source_format", sa.String(length=20), nullable=False),
        sa.Column("parser_version", sa.String(length=30), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("sheet", sa.String(length=255), nullable=True),
        sa.Column("header_row", sa.Integer(), nullable=True),
        sa.Column("projectlist_po_state", sa.String(length=20), nullable=True),
        sa.Column("selected_rows", sa.Integer(), nullable=False),
        sa.Column("ignored_rows", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("skipped_duplicate", sa.Integer(), nullable=False),
        sa.Column("skipped_settled", sa.Integer(), nullable=False),
        sa.Column("source_conflicts", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_po_import_batches_created_at",
        "po_import_batches",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_po_import_batches_file_hash",
        "po_import_batches",
        ["file_hash"],
        unique=False,
    )
    op.create_index(
        "ix_po_import_batches_source_format",
        "po_import_batches",
        ["source_format"],
        unique=False,
    )
    op.create_table(
        "po_import_row_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("sheet", sa.String(length=255), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("po_id", sa.Integer(), nullable=True),
        sa.Column("translator_id", sa.Integer(), nullable=True),
        sa.Column("translator_name", sa.String(length=200), nullable=True),
        sa.Column("project", sa.String(length=200), nullable=True),
        sa.Column("settlement_month", sa.String(length=7), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("source_lang", sa.String(length=20), nullable=True),
        sa.Column("target_lang", sa.String(length=20), nullable=True),
        sa.Column("pricing_mode", sa.String(length=20), nullable=True),
        sa.Column("word_count", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("rate", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("source_fee_cny", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("source_key", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('imported', 'skip_duplicate', 'skip_settled', "
            "'source_conflict', 'invalid', 'ignored')",
            name="ck_po_import_row_logs_action",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["po_import_batches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "sheet",
            "source_row",
            name="uq_po_import_row_logs_batch_sheet_row",
        ),
    )
    op.create_index(
        "ix_po_import_row_logs_action",
        "po_import_row_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_po_import_row_logs_batch_id",
        "po_import_row_logs",
        ["batch_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_po_import_row_logs_batch_id",
        table_name="po_import_row_logs",
    )
    op.drop_index(
        "ix_po_import_row_logs_action",
        table_name="po_import_row_logs",
    )
    op.drop_table("po_import_row_logs")
    op.drop_index(
        "ix_po_import_batches_source_format",
        table_name="po_import_batches",
    )
    op.drop_index(
        "ix_po_import_batches_file_hash",
        table_name="po_import_batches",
    )
    op.drop_index(
        "ix_po_import_batches_created_at",
        table_name="po_import_batches",
    )
    op.drop_table("po_import_batches")
