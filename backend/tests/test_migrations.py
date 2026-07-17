"""Alembic migration and legacy-baseline regression tests."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"
EXPECTED_TABLES = {
    "audit_logs",
    "capacity_allocations",
    "complaints",
    "contracts",
    "language_pairs",
    "payment_infos",
    "pending_changes",
    "pending_idempotency",
    "po_settlements",
    "quality_scores",
    "rate_changes",
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


def check_empty_database_upgrade(tmpdir):
    db_path = Path(tmpdir) / "empty.db"
    result = run("-m", "alembic", "-c", str(ALEMBIC_CONFIG), "upgrade", "head",
                 db_path=db_path)
    assert_ok(result)

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES | {"alembic_version"} == tables
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
        check_application_import_does_not_create_schema(tmpdir)
        check_existing_database_baseline(tmpdir)
        check_baseline_safety_guards(tmpdir)
        check_known_legacy_missing_table_is_repaired(tmpdir)
    print("alembic migrations and legacy baseline pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
