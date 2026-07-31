"""历史数据质量审计回归测试。"""

from sqlalchemy import create_engine, text

from app.data_quality import audit_connection


def main():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE translators (id INTEGER PRIMARY KEY, onboarding_date VARCHAR(20), last_contact VARCHAR(20))"))
        conn.execute(text("CREATE TABLE contracts (id INTEGER PRIMARY KEY, expiry_date VARCHAR(20))"))
        conn.execute(text("CREATE TABLE po_settlements (id INTEGER PRIMARY KEY, settlement_month VARCHAR(7))"))
        conn.execute(text("CREATE TABLE capacity_month_overrides (id INTEGER PRIMARY KEY, month VARCHAR(7))"))
        conn.execute(text("""
            INSERT INTO translators (id, onboarding_date, last_contact)
            VALUES (1, '2025-01-32', '2026-06-01'), (2, '2025-01-01', '2026-02-30')
        """))
        conn.execute(text("INSERT INTO contracts (id, expiry_date) VALUES (1, '2026-02-30')"))
        conn.execute(text("INSERT INTO po_settlements (id, settlement_month) VALUES (1, '2026-13')"))
        conn.execute(text("INSERT INTO capacity_month_overrides (id, month) VALUES (1, '2026-13')"))
        issues = audit_connection(conn)

    keys = {(i["table"], i["row_id"], i["field"], i["suggested_action"]) for i in issues}
    expected = {
        ("translators", 1, "onboarding_date", "manual_fix"),
        ("translators", 2, "last_contact", "clear_nullable"),
        ("contracts", 1, "expiry_date", "clear_nullable"),
        ("po_settlements", 1, "settlement_month", "manual_fix"),
        ("capacity_month_overrides", 1, "month", "manual_fix"),
    }
    missing = expected - keys
    if missing:
        print("缺少问题:", sorted(missing))
        return 1
    print("data quality audit reports invalid existing values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
