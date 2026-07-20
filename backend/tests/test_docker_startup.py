"""Docker entrypoint regression tests."""

import os
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = PROJECT_ROOT / "backend" / "docker-entrypoint.sh"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"
DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"


def make_fake_commands(tmpdir):
    bin_dir = Path(tmpdir) / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.write_text(
        "#!/bin/sh\n"
        "printf 'python:%s DB_URL=%s\\n' \"$*\" \"$DB_URL\" >> \"$STARTUP_LOG\"\n"
        "exit \"${FAKE_ALEMBIC_EXIT:-0}\"\n"
    )
    uvicorn = bin_dir / "uvicorn"
    uvicorn.write_text(
        "#!/bin/sh\n"
        "printf 'uvicorn:%s\\n' \"$*\" >> \"$STARTUP_LOG\"\n"
    )
    python.chmod(0o755)
    uvicorn.chmod(0o755)
    return bin_dir


def run_entrypoint(tmpdir, **overrides):
    log_path = Path(tmpdir) / "startup.log"
    env = os.environ.copy()
    env.update(
        {
            "APP_DIR": str(PROJECT_ROOT / "backend"),
            "PATH": f"{make_fake_commands(tmpdir)}:{env['PATH']}",
            "STARTUP_LOG": str(log_path),
        }
    )
    env.update(overrides)
    result = subprocess.run(
        ["sh", str(ENTRYPOINT)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return result, log_path.read_text() if log_path.exists() else ""


def check_missing_secret_stops_before_migration():
    with tempfile.TemporaryDirectory(prefix="docker-startup-") as tmpdir:
        result, log = run_entrypoint(tmpdir, JWT_SECRET="", AES_KEY="")
    assert result.returncode != 0
    assert "JWT_SECRET must be set" in result.stderr
    assert log == ""


def check_missing_aes_key_stops_before_migration():
    with tempfile.TemporaryDirectory(prefix="docker-startup-") as tmpdir:
        result, log = run_entrypoint(tmpdir, JWT_SECRET="test-jwt", AES_KEY="")
    assert result.returncode != 0
    assert "AES_KEY must be set" in result.stderr
    assert log == ""


def check_migration_failure_stops_before_uvicorn():
    with tempfile.TemporaryDirectory(prefix="docker-startup-") as tmpdir:
        result, log = run_entrypoint(
            tmpdir,
            JWT_SECRET="test-jwt",
            AES_KEY="0" * 64,
            FAKE_ALEMBIC_EXIT="12",
        )
    assert result.returncode == 12
    assert "python:-m alembic -c alembic.ini upgrade head" in log
    assert "uvicorn:" not in log


def check_successful_migration_starts_uvicorn_with_persistent_sqlite_default():
    with tempfile.TemporaryDirectory(prefix="docker-startup-") as tmpdir:
        result, log = run_entrypoint(
            tmpdir,
            JWT_SECRET="test-jwt",
            AES_KEY="0" * 64,
        )
    assert result.returncode == 0
    assert "python:-m alembic -c alembic.ini upgrade head DB_URL=sqlite:////data/app.db" in log
    assert "uvicorn:app.main:app --host 0.0.0.0 --port 8000" in log


def check_docker_files_package_required_assets_without_secrets():
    dockerfile = DOCKERFILE.read_text()
    compose = COMPOSE_FILE.read_text()
    dockerignore_patterns = {
        line.strip()
        for line in DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY backend/alembic.ini backend/" in dockerfile
    assert "COPY backend/migrations/ backend/migrations/" in dockerfile
    assert "COPY backend/app/ backend/app/" in dockerfile
    assert "COPY frontend/ frontend/" in dockerfile
    assert "JWT_SECRET=" not in dockerfile
    assert "AES_KEY=" not in dockerfile
    assert "ENTRYPOINT [\"/app/backend/docker-entrypoint.sh\"]" in dockerfile
    assert "ENV TOKEN_TTL=28800" in dockerfile
    assert "./data:/data" in compose
    assert "sqlite:////data/app.db" in compose
    assert "TOKEN_TTL:" not in compose
    assert "sites-demo/" in dockerignore_patterns


def main():
    check_missing_secret_stops_before_migration()
    check_missing_aes_key_stops_before_migration()
    check_migration_failure_stops_before_uvicorn()
    check_successful_migration_starts_uvicorn_with_persistent_sqlite_default()
    check_docker_files_package_required_assets_without_secrets()
    print("docker startup tests pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
