"""译员管理系统 demo 验收测试（可重跑）。

先启动服务：backend/ 下 ./run.sh
再另开终端：.venv/bin/python tests/test_acceptance.py
覆盖：鉴权/RBAC、边界健壮、PRD 硬规则（邮箱唯一/金额验算/汇总/汇总字段自动算）、
安全（加密脱敏/明文权限）、agent 护栏（钱相关进待审）。绕本机 Clash 代理直连。
"""
import io
import json
import sys
import time
import urllib.error
import urllib.request

from openpyxl import Workbook

BASE = "http://127.0.0.1:8000"
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def req(m, p, body=None, token=None, raw=None, ct="application/json"):
    h = {}
    if token:
        h["Authorization"] = "Bearer " + token
    if raw is not None:
        data, h["Content-Type"] = raw, ct
    elif body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), ct
    else:
        data = None
    r = urllib.request.Request(BASE + p, data=data, method=m, headers=h)
    with OP.open(r, timeout=8) as x:
        c = x.headers.get("content-type", "")
        return x.status, (json.loads(x.read().decode() or "null") if "json" in c else x.read())


def code(fn):
    try:
        fn()
        return "no-error"
    except urllib.error.HTTPError as e:
        return e.code


def mk_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def mp(xb):
    bd = "--x"
    head = (f"--{bd}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"x.xlsx\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    return head + xb + f"\r\n--{bd}--\r\n".encode(), f"multipart/form-data; boundary={bd}"


def main():
    for _ in range(40):
        try:
            OP.open(BASE + "/api/overview", timeout=2)
            break
        except Exception:
            time.sleep(0.3)
    else:
        print("✗ 服务没起来，先 .venv/bin/python app.py")
        return 1

    ok = []

    def chk(n, c, e=""):
        ok.append(bool(c))
        print(("✓" if c else "✗ 失败:"), n, e)

    _, ED = req("POST", "/api/login", {"user": "资源端"}); ET = ED["token"]
    _, BO = req("POST", "/api/login", {"user": "boss"}); BT = BO["token"]
    _, AG = req("POST", "/api/login", {"user": "资源端Agent"}); AT = AG["token"]

    print("=== A 鉴权/RBAC ===")
    chk("登录不存在用户404", code(lambda: req("POST", "/api/login", {"user": "鬼"})) == 404)
    chk("坏token写403", code(lambda: req("POST", "/api/translators", {"name": "X"}, token="bad")) == 403)
    chk("无token写403", code(lambda: req("POST", "/api/translators", {"name": "X"})) == 403)
    chk("boss写403", code(lambda: req("POST", "/api/translators/1/capacity",
        {"period_year": 2026, "period_month": 6, "week_no": 1, "occupancy_pct": 1}, token=BT)) == 403)
    chk("agent不能批准403", code(lambda: req("POST", "/api/pending/1/approve", token=AT)) == 403)
    chk("viewer看审计403", code(lambda: req("GET", "/api/audit", token=BT)) == 403)

    print("=== B 边界/健壮 ===")
    chk("缺name 422", code(lambda: req("POST", "/api/translators", {"email": "a@b.c"}, token=ET)) == 422)
    chk("非法PO状态400", code(lambda: req("PUT", "/api/po/1/status", {"status": "乱填"}, token=ET)) == 400)
    chk("改不存在PO状态404", code(lambda: req("PUT", "/api/po/99999/status", {"status": "已支付"}, token=ET)) == 404)
    chk("操作不存在译员404", code(lambda: req("POST", "/api/translators/9999/rate-changes", {"change_date": "x"}, token=ET)) == 404)
    chk("批准不存在待审404", code(lambda: req("POST", "/api/pending/9999/approve", token=ET)) == 404)
    chk("不存在译员子表GET空", req("GET", "/api/translators/9999/quality")[1] == [])
    chk("空月PO汇总不崩", isinstance(req("GET", "/api/po/summary?month=1999-01")[1]["by_currency"], dict))
    bad_raw, bad_ct = mp(mk_xlsx([["乱"]]))
    chk("LQE非汇总表400", code(lambda: req("POST", "/api/import/lqe", raw=bad_raw, token=ET, ct=bad_ct)) == 400)

    print("=== C PRD 硬规则 ===")
    req("POST", "/api/translators", {"name": "唯A", "email": "dup@x.com", "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)
    chk("create重复邮箱400", code(lambda: req("POST", "/api/translators", {"name": "唯B", "email": "dup@x.com", "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 400)
    chk("update改成已存在邮箱400", code(lambda: req("PUT", "/api/translators/1", {"name": "张明", "email": "dup@x.com", "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 400)
    imp_raw, imp_ct = mp(mk_xlsx([["name", "email"], ["导入新", "new@x.com"], ["导入重", "dup@x.com"]]))
    _, imp = req("POST", "/api/import/translators", raw=imp_raw, token=ET, ct=imp_ct)
    chk("导入按邮箱去重(2行只进1)", imp["imported"] == 1, imp)
    _, po = req("GET", "/api/po?month=2026-06")
    chk("金额验算抓1行(410≠400)", len([p for p in po if not p["amount_ok"]]) == 1)
    _, sm = req("GET", "/api/po/summary?month=2026-06")
    chk("待付=Σ未开票+Σ已开票待付=2500", sm["by_currency"]["CNY"]["unpaid"] == 2500)
    req("POST", "/api/translators/2/rate-changes", {"change_date": "2026-06-25", "task_type": "翻译", "new_rate": 260}, token=ET)
    chk("翻译调价同步主表260", [t for t in req("GET", "/api/translators")[1] if t["id"] == 2][0]["translation_rate"] == 260)

    print("=== D 安全（加密脱敏）===")
    _, pm = req("GET", "/api/translators/1/payment")
    chk("银行账号脱敏", pm["bank_account"].startswith("*") and pm["bank_account"].endswith("5678"))
    _, pf = req("GET", "/api/translators/1/payment/reveal", token=ET)
    chk("editor看明文全号", pf["bank_account"] == "6225888812345678")
    chk("viewer看明文403", code(lambda: req("GET", "/api/translators/1/payment/reveal", token=BT)) == 403)

    print("=== E agent 护栏 ===")
    _, pr = req("POST", "/api/translators/1/rate-changes", {"change_date": "2026-06-25", "task_type": "翻译", "new_rate": 777}, token=AT)
    chk("agent费率→待审", pr.get("pending") is True)
    chk("待审期间主表未变", [t for t in req("GET", "/api/translators")[1] if t["id"] == 1][0]["translation_rate"] == 180)
    req("POST", f"/api/pending/{pr['pending_id']}/reject", token=ET)
    chk("驳回后待审清空", len(req("GET", "/api/pending", token=ET)[1]) == 0)
    req("POST", "/api/translators/1/capacity", {"period_year": 2026, "period_month": 6, "week_no": 2, "project": "agent", "occupancy_pct": 30}, token=AT)
    chk("agent档期直接落", any(w["period"] == "2026-06 W2" for w in req("GET", "/api/translators/1/capacity")[1]["weeks"]))

    print("=== F 优化校验（枚举/唯一性）===")
    chk("非法译员状态422", code(lambda: req("POST", "/api/translators", {"name": "状态X", "status": "乱", "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 422)
    chk("非法客诉严重度422", code(lambda: req("POST", "/api/translators/1/complaints", {"severity": "乱"}, token=ET)) == 422)
    chk("重复合同编号400", code(lambda: req("POST", "/api/translators/1/contracts", {"contract_number": "C-2025-011"}, token=ET)) == 400)
    chk("重复PO号400", code(lambda: req("POST", "/api/po", {"translator_id": 1, "settlement_month": "2026-07", "po_number": "PO-202606-001"}, token=ET)) == 400)

    print("=== G 主表联动（PRD §6.3.3/§12.3.2）===")
    def tr(i): return [t for t in req("GET", "/api/translators")[1] if t["id"] == i][0]
    b3 = tr(3)
    req("POST", "/api/translators/3/complaints", {"date": "2026-06-20", "complaint_type": "质量不达标", "severity": "一般", "deduction_amount": 150}, token=ET)
    a3 = tr(3)
    chk("客诉联动 次数+1", a3["complaint_count"] == (b3["complaint_count"] or 0) + 1)
    chk("客诉联动 扣款累加150", round(a3["deduction_total"] - (b3["deduction_total"] or 0), 2) == 150)
    req("POST", "/api/translators/3/quality", {"evaluation_period": "2026-06", "score": 88, "minor_errors": 2}, token=ET)
    req("POST", "/api/translators/3/quality", {"evaluation_period": "2026-07", "score": 92, "minor_errors": 1}, token=ET)
    q3 = tr(3)
    chk("质量联动 最近分=92", q3["recent_qa_score"] == 92)
    chk("质量联动 累计均分=90", q3["cumulative_qa_score"] == 90)
    chk("质量联动 低错累计=3", q3["low_error_count"] == 3)
    chk("谈判联动 成功后谈后费率", (lambda t: (req("POST", "/api/translators/3/rate-changes", {"change_date": "2026-06-25", "task_type": "翻译", "original_rate": 150, "new_rate": 140, "result": "成功"}, token=ET), tr(3))[1]["post_negotiation_rate"] == 140)(None))

    print()
    print("结果:", f"{sum(ok)}/{len(ok)} 全通过 ✅" if all(ok) else f"{sum(ok)}/{len(ok)}（有失败）")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
