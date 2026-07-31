"""Backfill legacy current projects into project experiences.

Revision ID: 20260728_0003
Revises: 20260724_0002
Create Date: 2026-07-28
"""

from alembic import op


revision = "20260728_0003"
down_revision = "20260724_0002"
branch_labels = None
depends_on = None

BACKFILL_REMARK = "由旧版当前项目字段迁移"


def upgrade():
    op.execute(f"""
        INSERT INTO translator_project_experiences
            (translator_id, cooperation_source, project_status, project_name,
             role, remarks)
        SELECT
            t.id, 'our_company', 'current', TRIM(t.current_project),
            t.role, '{BACKFILL_REMARK}'
        FROM translators AS t
        WHERE t.deleted_at IS NULL
          AND t.current_project IS NOT NULL
          AND TRIM(t.current_project) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM translator_project_experiences AS p
              WHERE p.translator_id = t.id
                AND p.project_status = 'current'
                AND p.project_name = TRIM(t.current_project)
          )
    """)


def downgrade():
    op.execute(f"""
        DELETE FROM translator_project_experiences
        WHERE remarks = '{BACKFILL_REMARK}'
    """)
