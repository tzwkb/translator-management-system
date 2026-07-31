"""Alembic migration and legacy-baseline regression tests."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Translator,
    TranslatorAlias,
    TranslatorProjectExperience,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"
INITIAL_REVISION = "20260717_0001"
HEAD_REVISION = "20260731_0006"
EXPECTED_TABLES = {
    "audit_logs",
    "capacity_allocations",
    "complaints",
    "contracts",
    "language_pairs",
    "payment_infos",
    "payment_accounts",
    "pending_changes",
    "pending_idempotency",
    "po_settlements",
    "project_prices",
    "quality_scores",
    "rate_changes",
    "translator_project_experiences",
    "translator_aliases",
    "translator_attachments",
    "translators",
}


def command_env(db_path):
    env = os.environ.copy()
    env["DB_URL"] = f"sqlite:///{db_path}"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env["AES_KEY"] = "0" * 64
    return env


def run(*args, db_path):
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=command_env(db_path),
        capture_output=True,
        text=True,
    )


def assert_ok(result):
    assert result.returncode == 0, result.stdout + result.stderr


def assert_profile_schema(engine):
    inspector = inspect(engine)
    alias_columns = {
        item["name"]: item
        for item in inspector.get_columns("translator_aliases")
    }
    assert set(alias_columns) == {
        "id", "translator_id", "alias", "normalized_alias", "created_at",
    }
    assert all(not item["nullable"] for item in alias_columns.values())
    alias_indexes = {
        item["name"] for item in inspector.get_indexes("translator_aliases")
    }
    assert alias_indexes == {"ix_translator_aliases_translator_id"}
    alias_unique = {
        item["name"]: item
        for item in inspector.get_unique_constraints("translator_aliases")
    }
    assert alias_unique["uq_translator_aliases_normalized_alias"][
        "column_names"
    ] == ["normalized_alias"]
    alias_foreign_keys = inspector.get_foreign_keys("translator_aliases")
    assert any(
        key["constrained_columns"] == ["translator_id"]
        and key["referred_table"] == "translators"
        and key["referred_columns"] == ["id"]
        for key in alias_foreign_keys
    )

    translator_columns = {
        item["name"]: item for item in inspector.get_columns("translators")
    }
    assert translator_columns["gender"]["nullable"]
    assert translator_columns["entity_type"]["nullable"]
    assert not translator_columns["settlement_mode"]["nullable"]
    assert {"manual_rating", "manual_rating_reason"} <= set(translator_columns)

    experience_columns = {
        item["name"]: item
        for item in inspector.get_columns("translator_project_experiences")
    }
    assert set(experience_columns) == {
        "id",
        "translator_id",
        "cooperation_source",
        "project_status",
        "project_name",
        "external_company",
        "role",
        "source_lang",
        "target_lang",
        "start_date",
        "end_date",
        "remaining_volume",
        "deadline",
        "remarks",
    }
    for required in (
        "translator_id",
        "cooperation_source",
        "project_status",
        "project_name",
    ):
        assert not experience_columns[required]["nullable"]
    foreign_keys = inspector.get_foreign_keys("translator_project_experiences")
    assert any(
        key["constrained_columns"] == ["translator_id"]
        and key["referred_table"] == "translators"
        and key["referred_columns"] == ["id"]
        for key in foreign_keys
    )
    indexes = {
        item["name"]
        for item in inspector.get_indexes("translator_project_experiences")
    }
    assert indexes == {
        "ix_translator_project_experiences_cooperation_source",
        "ix_translator_project_experiences_project_status",
        "ix_translator_project_experiences_translator_id",
    }

    po_columns = {
        item["name"]: item for item in inspector.get_columns("po_settlements")
    }
    assert {"pricing_mode", "source_key", "source_name", "source_row"} <= set(po_columns)
    assert not po_columns["pricing_mode"]["nullable"]
    po_indexes = {
        item["name"]: item for item in inspector.get_indexes("po_settlements")
    }
    assert po_indexes["ix_po_settlements_source_key"]["unique"]

    project_price_columns = {
        item["name"] for item in inspector.get_columns("project_prices")
    }
    assert {
        "id", "translator_id", "project_experience_id", "project_name",
        "source_lang", "target_lang", "price_type", "task_type",
        "custom_task_name", "amount", "unit", "currency", "remarks",
    } == project_price_columns

    payment_column_rows = {
        item["name"]: item for item in inspector.get_columns("payment_accounts")
    }
    payment_columns = set(payment_column_rows)
    assert {
        "id", "translator_id", "method", "currency", "account_name",
        "account_number_enc", "bank_name", "bank_address", "swift_code",
        "routing_code", "tax_id_enc", "qr_stored_name", "qr_original_name",
        "qr_mime", "is_default", "remarks",
    } == payment_columns
    assert payment_column_rows["account_name"]["nullable"]
    payment_indexes = {
        item["name"]: item for item in inspector.get_indexes("payment_accounts")
    }
    assert "ux_payment_accounts_default" not in payment_indexes

    quality_columns = {
        item["name"] for item in inspector.get_columns("quality_scores")
    }
    assert {"is_qualified", "failure_reason"} <= quality_columns

    attachment_columns = {
        item["name"] for item in inspector.get_columns("translator_attachments")
    }
    assert {
        "id", "translator_id", "category", "original_name", "stored_name",
        "mime_type", "size_bytes", "sha256", "created_at",
    } == attachment_columns


def check_empty_database_upgrade(tmpdir):
    db_path = Path(tmpdir) / "empty.db"
    result = run("-m", "alembic", "-c", str(ALEMBIC_CONFIG), "upgrade", "head",
                 db_path=db_path)
    assert_ok(result)

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES | {"alembic_version"} == tables
    assert_profile_schema(engine)
    indexes = {item["name"] for item in inspector.get_indexes("pending_changes")}
    assert "ux_pending_actor_idempotency" in indexes
    assert "ux_pending_active_fingerprint" in indexes
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT COUNT(*) FROM translators")) == 0
        version = conn.scalar(text("SELECT version_num FROM alembic_version"))
    assert version

    result = run("-m", "alembic", "-c", str(ALEMBIC_CONFIG), "downgrade", "base",
                 db_path=db_path)
    assert_ok(result)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT COUNT(*) FROM alembic_version")) == 0

    result = run("-m", "alembic", "-c", str(ALEMBIC_CONFIG), "upgrade", "head",
                 db_path=db_path)
    assert_ok(result)


def check_initial_revision_upgrade_round_trip(tmpdir):
    db_path = Path(tmpdir) / "initial-revision.db"
    result = run(
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_CONFIG),
        "upgrade",
        INITIAL_REVISION,
        db_path=db_path,
    )
    assert_ok(result)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO translators
                (id, name, status, low_error_count, current_project, role,
                 cumulative_word_count, cumulative_unpaid, complaint_count,
                 deduction_total)
            VALUES
                (7, '保留数据', 'Active', 0, '旧当前项目', '翻译', 0, 0, 0, 0)
        """))

    result = run(
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_CONFIG),
        "upgrade",
        "head",
        db_path=db_path,
    )
    assert_ok(result)
    assert_profile_schema(engine)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT name, gender, entity_type
            FROM translators WHERE id = 7
        """)).one()
        assert tuple(row) == ("保留数据", None, None)
        project = conn.execute(text("""
            SELECT translator_id, cooperation_source, project_status,
                   project_name, role, remarks
            FROM translator_project_experiences
        """)).one()
        assert tuple(project) == (
            7, "our_company", "current", "旧当前项目", "翻译",
            "由旧版当前项目字段迁移",
        )
        assert conn.scalar(text("PRAGMA integrity_check")) == "ok"
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION
    with Session(engine) as session:
        translator = session.get(Translator, 7)
        assert translator is not None
        assert translator.gender is None
        assert translator.entity_type is None
        assert translator.as_dict()["current_project"] == "旧当前项目"
        session.add(TranslatorAlias(
            translator_id=7,
            alias="Legacy Name",
            normalized_alias="legacy name",
        ))
        session.commit()
        assert session.scalar(
            select(TranslatorAlias).where(
                TranslatorAlias.translator_id == 7
            )
        ).alias == "Legacy Name"
        project = session.scalar(
            select(TranslatorProjectExperience).where(
                TranslatorProjectExperience.translator_id == 7
            )
        )
        assert project is not None
        assert project.project_name == "旧当前项目"

    result = run(
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_CONFIG),
        "check",
        db_path=db_path,
    )
    assert_ok(result)
    assert "No new upgrade operations detected" in result.stdout

    result = run(
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_CONFIG),
        "downgrade",
        INITIAL_REVISION,
        db_path=db_path,
    )
    assert_ok(result)
    inspector = inspect(engine)
    assert "translator_project_experiences" not in inspector.get_table_names()
    translator_columns = {
        item["name"] for item in inspector.get_columns("translators")
    }
    assert "gender" not in translator_columns
    assert "entity_type" not in translator_columns
    with engine.connect() as conn:
        assert conn.scalar(
            text("SELECT current_project FROM translators WHERE id = 7")
        ) == "旧当前项目"
        assert conn.scalar(text("PRAGMA integrity_check")) == "ok"
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == INITIAL_REVISION

    result = run(
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_CONFIG),
        "upgrade",
        "head",
        db_path=db_path,
    )
    assert_ok(result)
    assert_profile_schema(engine)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT name FROM translators WHERE id = 7")) == "保留数据"
        assert conn.scalar(text("PRAGMA integrity_check")) == "ok"


def check_application_import_does_not_create_schema(tmpdir):
    db_path = Path(tmpdir) / "import-only.db"
    result = run("-c", "import app.main", db_path=db_path)
    assert_ok(result)
    engine = create_engine(f"sqlite:///{db_path}")
    assert inspect(engine).get_table_names() == []


def check_existing_database_baseline(tmpdir):
    db_path = Path(tmpdir) / "existing.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO translators
                (id, name, status, low_error_count, cumulative_word_count,
                 cumulative_unpaid, complaint_count, deduction_total)
            VALUES (7, '保留数据', 'Active', 0, 0, 0, 0, 0)
        """))

    result = run("-m", "app.db_baseline", "--backup-confirmed", db_path=db_path)
    assert_ok(result)

    inspector = inspect(engine)
    assert EXPECTED_TABLES | {"alembic_version"} == set(inspector.get_table_names())
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT name FROM translators WHERE id=7")) == "保留数据"
        assert conn.scalar(text("SELECT version_num FROM alembic_version"))


def check_baseline_safety_guards(tmpdir):
    db_path = Path(tmpdir) / "guard.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE translators (id INTEGER PRIMARY KEY)"))

    missing_confirmation = run("-m", "app.db_baseline", db_path=db_path)
    assert missing_confirmation.returncode != 0
    assert "--backup-confirmed" in missing_confirmation.stderr

    incomplete_schema = run(
        "-m", "app.db_baseline", "--backup-confirmed", db_path=db_path
    )
    assert incomplete_schema.returncode != 0
    assert "表集与当前模型不一致" in incomplete_schema.stderr
    assert "alembic_version" not in inspect(engine).get_table_names()


def check_known_legacy_missing_table_is_repaired(tmpdir):
    db_path = Path(tmpdir) / "legacy-eleven-tables.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE pending_idempotency"))

    result = run("-m", "app.db_baseline", "--backup-confirmed", db_path=db_path)
    assert_ok(result)
    assert EXPECTED_TABLES | {"alembic_version"} == set(inspect(engine).get_table_names())


def main():
    with tempfile.TemporaryDirectory(prefix="alembic-tests-") as tmpdir:
        check_empty_database_upgrade(tmpdir)
        check_initial_revision_upgrade_round_trip(tmpdir)
        check_application_import_does_not_create_schema(tmpdir)
        check_existing_database_baseline(tmpdir)
        check_baseline_safety_guards(tmpdir)
        check_known_legacy_missing_table_is_repaired(tmpdir)
    print("alembic migrations and legacy baseline pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
