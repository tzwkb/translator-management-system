"""Complete the 13-item feedback data model.

Revision ID: 20260729_0004
Revises: 20260728_0003
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260729_0004"
down_revision = "20260728_0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("translators") as batch_op:
        batch_op.add_column(
            sa.Column(
                "settlement_mode", sa.String(20), nullable=False,
                server_default="monthly",
            )
        )

    with op.batch_alter_table("po_settlements") as batch_op:
        batch_op.add_column(
            sa.Column(
                "pricing_mode", sa.String(20), nullable=False,
                server_default="per_1000",
            )
        )
        batch_op.add_column(sa.Column("source_key", sa.String(64)))
        batch_op.add_column(sa.Column("source_name", sa.String(255)))
        batch_op.add_column(sa.Column("source_row", sa.Integer()))
    op.create_index(
        "ix_po_settlements_source_key",
        "po_settlements",
        ["source_key"],
        unique=True,
    )

    op.create_table(
        "project_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "translator_id", sa.Integer(),
            sa.ForeignKey("translators.id"), nullable=False,
        ),
        sa.Column(
            "project_experience_id", sa.Integer(),
            sa.ForeignKey("translator_project_experiences.id"),
        ),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("source_lang", sa.String(20)),
        sa.Column("target_lang", sa.String(20)),
        sa.Column("price_type", sa.String(20), nullable=False),
        sa.Column("task_type", sa.String(50)),
        sa.Column("custom_task_name", sa.String(100)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("remarks", sa.Text()),
    )
    op.create_index(
        "ix_project_prices_translator_id",
        "project_prices",
        ["translator_id"],
    )
    op.create_index(
        "ix_project_prices_price_type",
        "project_prices",
        ["price_type"],
    )

    op.create_table(
        "payment_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "translator_id", sa.Integer(),
            sa.ForeignKey("translators.id"), nullable=False,
        ),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(10)),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("account_number_enc", sa.LargeBinary()),
        sa.Column("bank_name", sa.String(200)),
        sa.Column("bank_address", sa.String(300)),
        sa.Column("swift_code", sa.String(50)),
        sa.Column("routing_code", sa.String(50)),
        sa.Column("tax_id_enc", sa.LargeBinary()),
        sa.Column("qr_stored_name", sa.String(120)),
        sa.Column("qr_original_name", sa.String(255)),
        sa.Column("qr_mime", sa.String(100)),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false(),
        ),
        sa.Column("remarks", sa.Text()),
    )
    op.create_index(
        "ix_payment_accounts_translator_id",
        "payment_accounts",
        ["translator_id"],
    )
    op.create_index(
        "ix_payment_accounts_method",
        "payment_accounts",
        ["method"],
    )
    op.create_index(
        "ux_payment_accounts_default",
        "payment_accounts",
        ["translator_id"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "translator_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "translator_id", sa.Integer(),
            sa.ForeignKey("translators.id"), nullable=False,
        ),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(120), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_translator_attachments_translator_id",
        "translator_attachments",
        ["translator_id"],
    )
    op.create_index(
        "ix_translator_attachments_category",
        "translator_attachments",
        ["category"],
    )

    op.execute("""
        INSERT INTO payment_accounts
            (translator_id, method, currency, account_name, account_number_enc,
             bank_name, tax_id_enc, is_default, remarks)
        SELECT
            p.translator_id, 'personal_bank', COALESCE(p.currency, 'CNY'),
            COALESCE(NULLIF(TRIM(p.payee_name), ''), t.name),
            p.bank_account_enc, p.bank_name, p.id_card_enc, 1,
            CASE
                WHEN p.supports_wechat = 1
                THEN COALESCE(p.remarks || '；', '') || '旧记录支持微信'
                ELSE p.remarks
            END
        FROM payment_infos AS p
        JOIN translators AS t ON t.id = p.translator_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payment_accounts AS a
            WHERE a.translator_id = p.translator_id
        )
    """)


def downgrade():
    op.drop_table("translator_attachments")
    op.drop_table("payment_accounts")
    op.drop_table("project_prices")
    op.drop_index("ix_po_settlements_source_key", table_name="po_settlements")
    with op.batch_alter_table("po_settlements") as batch_op:
        batch_op.drop_column("source_row")
        batch_op.drop_column("source_name")
        batch_op.drop_column("source_key")
        batch_op.drop_column("pricing_mode")
    with op.batch_alter_table("translators") as batch_op:
        batch_op.drop_column("settlement_mode")
