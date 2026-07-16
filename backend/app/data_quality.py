"""历史数据质量审计。"""

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

DATE_FIELDS = (
    ("translators", "id", "onboarding_date", True),
    ("translators", "id", "rate_confirmed_date", False),
    ("translators", "id", "contract_expiry", False),
    ("translators", "id", "last_negotiation_date", False),
    ("translators", "id", "last_contact", False),
    ("rate_changes", "id", "change_date", True),
    ("language_pairs", "id", "rate_confirmed_date", False),
    ("contracts", "id", "sign_date", False),
    ("contracts", "id", "expiry_date", False),
    ("contracts", "id", "nda_expiry", False),
    ("complaints", "id", "date", False),
)

MONTH_FIELDS = (
    ("po_settlements", "id", "settlement_month", True),
    ("quality_scores", "id", "evaluation_period", False),
)

RANGE_FIELDS = (
    ("capacity_allocations", "id", "period_year", 1900, 2100),
    ("capacity_allocations", "id", "period_month", 1, 12),
    ("capacity_allocations", "id", "week_no", 1, 6),
    ("capacity_allocations", "id", "occupancy_pct", 0, 100),
)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _validate_date(value: Any, *, required: bool) -> str | None:
    if _blank(value):
        return "必填字段为空" if required else None
    value = str(value).strip()
    if not DATE_RE.fullmatch(value):
        return "日期格式应为 YYYY-MM-DD"
    try:
        date.fromisoformat(value)
    except ValueError:
        return "日期不存在"
    return None


def _validate_month(value: Any, *, required: bool) -> str | None:
    if _blank(value):
        return "必填字段为空" if required else None
    value = str(value).strip()
    if not MONTH_RE.fullmatch(value):
        return "月份格式应为 YYYY-MM"
    month = int(value.split("-")[1])
    if not 1 <= month <= 12:
        return "月份不存在"
    return None


def _validate_integer_range(value: Any, lower: int, upper: int) -> str | None:
    if _blank(value):
        return "必填字段为空"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return f"应为 {lower}-{upper} 的整数"
    if str(value).strip() != str(number):
        return f"应为 {lower}-{upper} 的整数"
    if not lower <= number <= upper:
        return f"应在 {lower}-{upper}"
    return None


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _make_issue(table: str, row_id: Any, field: str, value: Any, reason: str, required: bool) -> dict[str, Any]:
    return {
        "table": table,
        "row_id": row_id,
        "field": field,
        "value": value,
        "reason": reason,
        "required": required,
        "suggested_action": "manual_fix" if required else "clear_nullable",
    }


def _table_columns(conn, table: str) -> set[str]:
    return {column["name"] for column in inspect(conn).get_columns(table)}


def _field_exists(conn, table: str, pk: str, field: str, tables: set[str]) -> bool:
    if table not in tables:
        return False
    columns = _table_columns(conn, table)
    return pk in columns and field in columns


def _scan_field(conn, table: str, pk: str, field: str):
    sql = text(f"SELECT {_quote_identifier(pk)}, {_quote_identifier(field)} FROM {_quote_identifier(table)}")
    return conn.execute(sql).fetchall()


def audit_connection(conn) -> list[dict[str, Any]]:
    """扫描当前连接中的历史非法日期、月份和范围字段。"""
    issues: list[dict[str, Any]] = []
    tables = set(inspect(conn).get_table_names())

    for table, pk, field, required in DATE_FIELDS:
        if not _field_exists(conn, table, pk, field, tables):
            continue
        for row_id, value in _scan_field(conn, table, pk, field):
            reason = _validate_date(value, required=required)
            if reason:
                issues.append(_make_issue(table, row_id, field, value, reason, required))

    for table, pk, field, required in MONTH_FIELDS:
        if not _field_exists(conn, table, pk, field, tables):
            continue
        for row_id, value in _scan_field(conn, table, pk, field):
            reason = _validate_month(value, required=required)
            if reason:
                issues.append(_make_issue(table, row_id, field, value, reason, required))

    for table, pk, field, lower, upper in RANGE_FIELDS:
        if not _field_exists(conn, table, pk, field, tables):
            continue
        for row_id, value in _scan_field(conn, table, pk, field):
            reason = _validate_integer_range(value, lower, upper)
            if reason:
                issues.append(_make_issue(table, row_id, field, value, reason, True))

    return issues


def format_issues(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "未发现历史非法日期、月份或范围数据。"
    lines = [f"发现 {len(issues)} 条历史数据问题："]
    action_text = {
        "manual_fix": "必填/业务关键字段，需要人工改成真实值",
        "clear_nullable": "可空字段，可清空为 NULL",
    }
    for issue in issues:
        action = action_text.get(issue["suggested_action"], issue["suggested_action"])
        lines.append(
            f"- {issue['table']}#{issue['row_id']}.{issue['field']} = {issue['value']!r}: "
            f"{issue['reason']}；{action}"
        )
    return "\n".join(lines)


def write_json_report(issues: list[dict[str, Any]], output: str | Path) -> None:
    Path(output).write_text(json.dumps(issues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="审计历史非法日期、月份和范围字段")
    parser.add_argument("--output", help="把问题列表写入 JSON 文件")
    parser.add_argument("--fail-on-issues", action="store_true", help="发现问题时返回非 0 退出码")
    args = parser.parse_args(argv)

    from .db import engine

    with engine.connect() as conn:
        issues = audit_connection(conn)
    if args.output:
        write_json_report(issues, args.output)
    print(format_issues(issues))
    return 1 if args.fail_on_issues and issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
