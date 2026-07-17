"""Create the initial application schema.

Revision ID: 20260717_0001
Revises:
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "translators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("wechat", sa.String(100)),
        sa.Column("email", sa.String(200)),
        sa.Column("location", sa.String(200)),
        sa.Column("timezone", sa.String(50)),
        sa.Column("native_language", sa.String(50)),
        sa.Column("onboarding_date", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(100)),
        sa.Column("language_pairs", sa.String(200)),
        sa.Column("translation_rate", sa.Numeric(10, 2)),
        sa.Column("mtpe_rate", sa.Numeric(10, 2)),
        sa.Column("review_rate", sa.Numeric(10, 2)),
        sa.Column("lqa_rate", sa.Numeric(10, 2)),
        sa.Column("rate_confirmed_date", sa.String(20)),
        sa.Column("domains", sa.Text()),
        sa.Column("text_types", sa.Text()),
        sa.Column("cat_tools", sa.Text()),
        sa.Column("internal_rating", sa.String(20)),
        sa.Column("trial_result", sa.String(50)),
        sa.Column("recent_qa_score", sa.Numeric(5, 2)),
        sa.Column("cumulative_qa_score", sa.Numeric(5, 2)),
        sa.Column("low_error_count", sa.Integer(), nullable=False),
        sa.Column("low_error_rate", sa.Numeric(10, 4)),
        sa.Column("current_project", sa.String(200)),
        sa.Column("role", sa.String(50)),
        sa.Column("daily_output", sa.Integer()),
        sa.Column("weekend_off", sa.Boolean()),
        sa.Column("availability", sa.String(50)),
        sa.Column("cumulative_word_count", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(10)),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("invoice_type", sa.String(50)),
        sa.Column("tax_deduction", sa.String(50)),
        sa.Column("cumulative_unpaid", sa.Numeric(12, 2), nullable=False),
        sa.Column("contract_status", sa.String(50)),
        sa.Column("contract_expiry", sa.String(20)),
        sa.Column("nda_signed", sa.Boolean()),
        sa.Column("negotiation_status", sa.String(50)),
        sa.Column("last_negotiation_date", sa.String(20)),
        sa.Column("post_negotiation_rate", sa.Numeric(10, 2)),
        sa.Column("rate_reduction_pct", sa.Numeric(5, 2)),
        sa.Column("accepted_reduction", sa.Boolean()),
        sa.Column("negotiation_notes", sa.Text()),
        sa.Column("punctuality_rate", sa.Numeric(5, 2)),
        sa.Column("responsiveness", sa.String(50)),
        sa.Column("complaint_count", sa.Integer(), nullable=False),
        sa.Column("deduction_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("cooperation_rating", sa.String(20)),
        sa.Column("last_contact", sa.String(20)),
        sa.Column("remarks", sa.Text()),
        sa.Column("deleted_at", sa.DateTime()),
    )
    op.create_index("ix_translators_status", "translators", ["status"])

    op.create_table(
        "rate_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("change_date", sa.String(20), nullable=False),
        sa.Column("source_lang", sa.String(20)),
        sa.Column("target_lang", sa.String(20)),
        sa.Column("task_type", sa.String(50)),
        sa.Column("original_rate", sa.Numeric(10, 2)),
        sa.Column("new_rate", sa.Numeric(10, 2)),
        sa.Column("negotiator", sa.String(100)),
        sa.Column("reason", sa.String(100)),
        sa.Column("result", sa.String(20)),
        sa.Column("remarks", sa.Text()),
    )
    op.create_index("ix_rate_changes_translator_id", "rate_changes", ["translator_id"])

    op.create_table(
        "po_settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("settlement_month", sa.String(7), nullable=False),
        sa.Column("project", sa.String(200)),
        sa.Column("source_lang", sa.String(20)),
        sa.Column("target_lang", sa.String(20)),
        sa.Column("role", sa.String(50)),
        sa.Column("word_count", sa.Numeric(12, 2)),
        sa.Column("rate", sa.Numeric(10, 2)),
        sa.Column("amount", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("po_number", sa.String(50)),
        sa.Column("remarks", sa.Text()),
    )
    op.create_index("ix_po_settlements_translator_id", "po_settlements", ["translator_id"])
    op.create_index("ix_po_settlements_settlement_month", "po_settlements", ["settlement_month"])
    op.create_index("ix_po_settlements_status", "po_settlements", ["status"])

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("contract_number", sa.String(100)),
        sa.Column("contract_type", sa.String(50)),
        sa.Column("sign_date", sa.String(20)),
        sa.Column("expiry_date", sa.String(20)),
        sa.Column("nda_signed", sa.Boolean(), nullable=False),
        sa.Column("nda_expiry", sa.String(20)),
        sa.Column("status", sa.String(20)),
        sa.Column("remarks", sa.Text()),
    )
    op.create_index("ix_contracts_translator_id", "contracts", ["translator_id"])

    op.create_table(
        "quality_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("evaluation_period", sa.String(20)),
        sa.Column("project", sa.String(200)),
        sa.Column("qa_type", sa.String(50)),
        sa.Column("score", sa.Numeric(5, 2)),
        sa.Column("critical_errors", sa.Integer(), nullable=False),
        sa.Column("major_errors", sa.Integer(), nullable=False),
        sa.Column("minor_errors", sa.Integer(), nullable=False),
        sa.Column("reviewer", sa.String(100)),
        sa.Column("feedback_notes", sa.Text()),
    )
    op.create_index("ix_quality_scores_translator_id", "quality_scores", ["translator_id"])

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("date", sa.String(20)),
        sa.Column("project", sa.String(200)),
        sa.Column("complaint_type", sa.String(50)),
        sa.Column("severity", sa.String(20)),
        sa.Column("deduction_amount", sa.Numeric(12, 2)),
        sa.Column("resolution", sa.String(50)),
        sa.Column("remarks", sa.Text()),
    )
    op.create_index("ix_complaints_translator_id", "complaints", ["translator_id"])

    op.create_table(
        "capacity_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("week_no", sa.Integer(), nullable=False),
        sa.Column("project", sa.String(200)),
        sa.Column("occupancy_pct", sa.Integer(), nullable=False),
    )
    op.create_index("ix_capacity_allocations_translator_id", "capacity_allocations", ["translator_id"])

    op.create_table(
        "payment_infos",
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), primary_key=True),
        sa.Column("currency", sa.String(10)),
        sa.Column("bank_name", sa.String(200)),
        sa.Column("bank_account_enc", sa.LargeBinary()),
        sa.Column("id_card_enc", sa.LargeBinary()),
        sa.Column("payee_name", sa.String(100)),
        sa.Column("supports_wechat", sa.Boolean(), nullable=False),
        sa.Column("remarks", sa.Text()),
    )

    op.create_table(
        "language_pairs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id"), nullable=False),
        sa.Column("source_lang", sa.String(20), nullable=False),
        sa.Column("target_lang", sa.String(20), nullable=False),
        sa.Column("translation_rate", sa.Numeric(10, 2)),
        sa.Column("mtpe_rate", sa.Numeric(10, 2)),
        sa.Column("review_rate", sa.Numeric(10, 2)),
        sa.Column("lqa_rate", sa.Numeric(10, 2)),
        sa.Column("lqe_rate", sa.Numeric(10, 2)),
        sa.Column("currency", sa.String(10)),
        sa.Column("rate_confirmed_date", sa.String(20)),
    )
    op.create_index("ix_language_pairs_translator_id", "language_pairs", ["translator_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user", sa.String(50)),
        sa.Column("action", sa.String(20)),
        sa.Column("entity", sa.String(50)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "pending_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by", sa.String(50)),
        sa.Column("kind", sa.String(30)),
        sa.Column("translator_id", sa.Integer()),
        sa.Column("payload", sa.Text()),
        sa.Column("idempotency_key", sa.String(160)),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_by", sa.String(50)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pending_changes_payload_hash", "pending_changes", ["payload_hash"])
    op.create_index(
        "ux_pending_actor_idempotency",
        "pending_changes",
        ["created_by", "idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ux_pending_active_fingerprint",
        "pending_changes",
        ["payload_hash"],
        unique=True,
        sqlite_where=sa.text("status = 'pending' AND payload_hash IS NOT NULL"),
    )

    op.create_table(
        "pending_idempotency",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("pending_change_id", sa.Integer(), sa.ForeignKey("pending_changes.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "created_by", "idempotency_key", name="uq_pending_idempotency_actor_key"
        ),
    )
    op.create_index(
        "ix_pending_idempotency_pending_change_id",
        "pending_idempotency",
        ["pending_change_id"],
    )


def downgrade():
    op.drop_table("pending_idempotency")
    op.drop_table("pending_changes")
    op.drop_table("audit_logs")
    op.drop_table("language_pairs")
    op.drop_table("payment_infos")
    op.drop_table("capacity_allocations")
    op.drop_table("complaints")
    op.drop_table("quality_scores")
    op.drop_table("contracts")
    op.drop_table("po_settlements")
    op.drop_table("rate_changes")
    op.drop_table("translators")
