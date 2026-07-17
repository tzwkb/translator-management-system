"""Validate and stamp an existing unversioned database as the Alembic baseline."""

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from . import models  # noqa: F401
from .db import Base, engine, prepare_legacy_schema_for_baseline


ALEMBIC_CONFIG = Path(__file__).resolve().parents[1] / "alembic.ini"


def validate_and_prepare_table_set():
    actual = set(inspect(engine).get_table_names())
    if "alembic_version" in actual:
        raise RuntimeError("数据库已由 Alembic 管理，不得重复打基线")
    expected = set(Base.metadata.tables)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    allowed_missing = {"pending_idempotency"}
    if set(missing) - allowed_missing or extra:
        raise RuntimeError(f"表集与当前模型不一致；缺失={missing}，多余={extra}")
    if "pending_idempotency" in missing:
        models.PendingIdempotency.__table__.create(engine)


def validate_metadata():
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "render_as_batch": True},
        )
        differences = compare_metadata(context, Base.metadata)
    if differences:
        details = "\n".join(repr(item) for item in differences)
        raise RuntimeError(f"历史整理后仍与当前模型不一致：\n{details}")


def stamp_baseline():
    validate_and_prepare_table_set()
    prepare_legacy_schema_for_baseline()
    validate_metadata()
    command.stamp(Config(str(ALEMBIC_CONFIG)), "head")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="整理、校验并接管无 Alembic 版本号的现有数据库"
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="确认已备份并完成恢复验证",
    )
    args = parser.parse_args(argv)
    if not args.backup_confirmed:
        parser.error("必须先备份并验证恢复，然后传入 --backup-confirmed")
    try:
        stamp_baseline()
    except Exception as exc:
        print(f"基线接管失败：{exc}", file=sys.stderr)
        return 1
    print("已校验历史数据库并记录 Alembic 初始基线")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
