"""Add translator invitations and reviewed submissions."""
from alembic import op
import sqlalchemy as sa

revision = "20260907_0009"
down_revision = "20260805_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "translator_intake_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id")),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    op.create_index("ix_translator_intake_invites_email", "translator_intake_invites", ["email"])
    op.create_table(
        "translator_intake_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invite_id", sa.Integer(), sa.ForeignKey("translator_intake_invites.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("reviewed_by", sa.String(100)),
        sa.Column("review_note", sa.Text()),
        sa.Column("translator_id", sa.Integer(), sa.ForeignKey("translators.id")),
        sa.CheckConstraint("status IN ('pending', 'needs_info', 'approved', 'rejected')",
                           name="ck_translator_intake_submissions_status"),
    )
    op.create_index("ix_translator_intake_submissions_status", "translator_intake_submissions", ["status"])


def downgrade():
    op.drop_index("ix_translator_intake_submissions_status", table_name="translator_intake_submissions")
    op.drop_table("translator_intake_submissions")
    op.drop_index("ix_translator_intake_invites_email", table_name="translator_intake_invites")
    op.drop_table("translator_intake_invites")
