"""译员管理系统 demo 验收测试（可重跑）。

直接运行：backend/.venv/bin/python backend/tests/test_acceptance.py
默认会启动临时 SQLite + 临时端口的隔离后端；若设置 BASE，则改为打指定外部服务。
覆盖：鉴权/RBAC、边界健壮、PRD 硬规则（邮箱唯一/金额验算/汇总/汇总字段自动算）、
安全（加密脱敏/明文权限）、agent 护栏（钱相关进待审）。绕本机 Clash 代理直连。
"""
import atexit
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import urllib.error
import urllib.request

from openpyxl import Workbook

BASE = os.getenv("BASE")
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SERVER = None
TMPDIR = None


def req(m, p, body=None, token=None, raw=None, ct="application/json", headers=None):
    h = dict(headers or {})
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


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stop_isolated_server():
    global SERVER, TMPDIR
    if SERVER and SERVER.poll() is None:
        SERVER.terminate()
        try:
            SERVER.wait(timeout=5)
        except subprocess.TimeoutExpired:
            SERVER.kill()
            SERVER.wait(timeout=5)
    if TMPDIR:
        TMPDIR.cleanup()
    SERVER = None
    TMPDIR = None


def start_isolated_server():
    global BASE, SERVER, TMPDIR
    if BASE:
        return
    backend_dir = Path(__file__).resolve().parents[1]
    TMPDIR = tempfile.TemporaryDirectory(prefix="translator-acceptance-")
    db_path = Path(TMPDIR.name) / "acceptance.db"
    port = free_port()
    BASE = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["DB_URL"] = f"sqlite:///{db_path}"
    env["JWT_SECRET"] = "acceptance-test-secret"
    env["AES_KEY"] = "0" * 64
    env["TOKEN_TTL"] = "3600"
    SERVER = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    atexit.register(stop_isolated_server)


def server_output():
    if not SERVER or not SERVER.stdout:
        return ""
    if SERVER.poll() is None:
        return "服务进程仍在运行，但未在超时时间内响应 /api/overview"
    try:
        return SERVER.stdout.read() or ""
    except Exception:
        return ""


def main():
    start_isolated_server()
    for _ in range(40):
        try:
            OP.open(BASE + "/api/overview", timeout=2)
            break
        except Exception:
            if SERVER and SERVER.poll() is not None:
                print("✗ 隔离服务启动失败")
                print(server_output())
                return 1
            time.sleep(0.3)
    else:
        print("✗ 服务没起来")
        print(server_output())
        return 1

    ok = []

    def chk(n, c, e=""):
        ok.append(bool(c))
        print(("✓" if c else "✗ 失败:"), n, e)

    _, ED = req("POST", "/api/login", {"user": "资源端"}); ET = ED["token"]
    _, BO = req("POST", "/api/login", {"user": "boss"}); BT = BO["token"]
    _, AG = req("POST", "/api/login", {"user": "资源端Agent"}); AT = AG["token"]
    run_tag = str(int(time.time() * 1000) % 100000)

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
    chk("操作不存在译员404", code(lambda: req("POST", "/api/translators/9999/rate-changes", {"change_date": "2026-06-01"}, token=ET)) == 404)
    chk("批准不存在待审404", code(lambda: req("POST", "/api/pending/9999/approve", token=ET)) == 404)
    chk("不存在译员子表GET空", req("GET", "/api/translators/9999/quality")[1] == [])
    chk("空月PO汇总不崩", isinstance(req("GET", "/api/po/summary?month=1999-01")[1]["by_currency"], dict))
    bad_raw, bad_ct = mp(mk_xlsx([["乱"]]))
    chk("LQE非汇总表400", code(lambda: req("POST", "/api/import/lqe", raw=bad_raw, token=ET, ct=bad_ct)) == 400)

    print("=== C PRD 硬规则 ===")
    dup_email = f"dup{run_tag}@x.com"
    new_email = f"new{run_tag}@x.com"
    req("POST", "/api/translators", {"name": "唯A", "email": dup_email, "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)
    chk("create重复邮箱400", code(lambda: req("POST", "/api/translators", {"name": "唯B", "email": dup_email, "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 400)
    chk("update改成已存在邮箱400", code(lambda: req("PUT", "/api/translators/1", {"name": "张明", "email": dup_email, "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 400)
    imp_raw, imp_ct = mp(mk_xlsx([
        ["name", "email", "native_language", "onboarding_date"],
        ["导入新", new_email, "中文", "2025-01-01"],
        ["导入重", dup_email, "中文", "2025-01-01"],
        ["导入坏", f"bad{run_tag}@x.com", "中文", "2025-01-32"],
    ]))
    _, imp = req("POST", "/api/import/translators", raw=imp_raw, token=ET, ct=imp_ct)
    chk("导入按邮箱去重(2行只进1)", imp["imported"] == 1, imp)
    chk("导入非法日期跳过并报告", len(imp.get("invalid_rows", [])) == 1, imp)
    _, po = req("GET", "/api/po?month=2026-06")
    chk("金额验算抓1行(410≠400)", len([p for p in po if not p["amount_ok"]]) == 1)
    _, sm = req("GET", "/api/po/summary?month=2026-06")
    chk("待付=Σ未开票+Σ已开票待付=2500", sm["by_currency"]["CNY"]["unpaid"] == 2500)
    req("POST", "/api/translators/2/rate-changes", {"change_date": "2026-06-25", "task_type": "翻译", "new_rate": 260}, token=ET)
    chk("翻译调价同步主表260", [t for t in req("GET", "/api/translators")[1] if t["id"] == 2][0]["translation_rate"] == 260)
    lp_target = "KO"
    req("POST", "/api/translators/1/language-pairs",
        {"source_lang": "ZH", "target_lang": lp_target, "translation_rate": 180, "review_rate": 90, "currency": "CNY"},
        token=ET)
    _, lps = req("GET", "/api/translators/1/language-pairs")
    zhko = next((x for x in lps if x["source_lang"] == "ZH" and x["target_lang"] == lp_target), {})
    chk("语言对可保存独立翻译费率", zhko.get("translation_rate") == 180, zhko)
    req("POST", "/api/translators/1/rate-changes",
        {"change_date": "2026-06-26", "source_lang": "ZH", "target_lang": lp_target, "task_type": "翻译", "new_rate": 188},
        token=ET)
    _, lps = req("GET", "/api/translators/1/language-pairs")
    zhko = next((x for x in lps if x["source_lang"] == "ZH" and x["target_lang"] == lp_target), {})
    chk("按语言对调价只更新该语言对", zhko.get("translation_rate") == 188, zhko)
    _, lp_po = req("POST", "/api/po",
                   {"translator_id": 1, "settlement_month": "2026-08", "source_lang": "ZH", "target_lang": lp_target,
                    "role": "翻译", "word_count": 1000, "po_number": "PO-LP-" + run_tag},
                   token=ET)
    chk("PO按语言对自动取价", lp_po.get("rate") == 188 and lp_po.get("amount") == 188 and lp_po.get("source_lang") == "ZH", lp_po)
    po_imp_raw, po_imp_ct = mp(mk_xlsx([
        ["译员", "结算月", "项目", "源语言", "目标语言", "角色", "字数", "单价", "币种", "状态", "PO号"],
        ["张明", "2026-09", "导入PO", "ZH", "EN", "翻译", 2000, None, "CNY", "未开票", "PO-IMP-" + run_tag],
        ["张明", "2026-09", "重复PO", "ZH", "EN", "翻译", 1000, 180, "CNY", "未开票", "PO-IMP-" + run_tag],
        ["不存在", "2026-09", "坏行", "ZH", "EN", "翻译", 1000, 180, "CNY", "未开票", "PO-BAD-" + run_tag],
    ]))
    try:
        _, po_imp = req("POST", "/api/import/po", raw=po_imp_raw, token=ET, ct=po_imp_ct)
    except urllib.error.HTTPError as e:
        po_imp = {"error": e.code}
    chk("PO导入支持有效/重复/错误行报告",
        po_imp.get("imported") == 1 and po_imp.get("skipped_dup_po") == 1 and len(po_imp.get("invalid_rows", [])) == 1,
        po_imp)
    _, imp_po_rows = req("GET", "/api/po?month=2026-09")
    imported_po = next((p for p in imp_po_rows if p.get("po_number") == "PO-IMP-" + run_tag), {})
    chk("PO导入可按语言对自动取价",
        imported_po.get("rate") == 180 and imported_po.get("amount") == 360,
        imported_po)
    chk("非法语言对400", code(lambda: req("POST", "/api/translators/1/language-pairs",
        {"source_lang": "ZH", "target_lang": "XX", "translation_rate": 1}, token=ET)) == 400)
    _, free_lp = req("POST", "/api/translators/1/language-pairs",
        {"source_lang": "EN", "target_lang": "JA", "translation_rate": 222, "currency": "CNY"},
        token=ET)
    chk("固定语言选项可自由组合", free_lp.get("source_lang") == "EN" and free_lp.get("target_lang") == "JA", free_lp)
    chk("源目标相同语言对400", code(lambda: req("POST", "/api/translators/1/language-pairs",
        {"source_lang": "ZH", "target_lang": "ZH", "translation_rate": 1}, token=ET)) == 400)

    print("=== D 安全（加密脱敏）===")
    _, pm = req("GET", "/api/translators/1/payment")
    chk("银行账号脱敏", pm["bank_account"].startswith("*") and pm["bank_account"].endswith("5678"))
    _, pf = req("GET", "/api/translators/1/payment/reveal", token=ET)
    chk("editor看明文全号", pf["bank_account"] == "6225888812345678")
    chk("viewer看明文403", code(lambda: req("GET", "/api/translators/1/payment/reveal", token=BT)) == 403)

    print("=== E agent 护栏 ===")
    pending_before = len(req("GET", "/api/pending", token=ET)[1])
    safe_rate = {"change_date": "2026-06-24", "source_lang": "ZH", "target_lang": "EN",
                 "task_type": "翻译", "new_rate": 771}
    safety_headers = {"Idempotency-Key": "acceptance:" + run_tag + ":rate",
                      "X-Dry-Run": "true"}
    _, rate_preview = req("POST", "/api/translators/1/rate-changes", safe_rate,
                          token=AT, headers=safety_headers)
    chk("agent费率dry-run不落待审",
        rate_preview.get("dry_run") is True and len(req("GET", "/api/pending", token=ET)[1]) == pending_before,
        rate_preview)

    safety_headers.pop("X-Dry-Run")
    _, safe_first = req("POST", "/api/translators/1/rate-changes", safe_rate,
                        token=AT, headers=safety_headers)
    _, safe_retry = req("POST", "/api/translators/1/rate-changes", safe_rate,
                        token=AT, headers=safety_headers)
    chk("agent同幂等键重试返回原待审",
        safe_retry.get("pending_id") == safe_first.get("pending_id") and safe_retry.get("deduplicated") is True,
        safe_retry)
    _, equivalent_same_key = req(
        "POST", "/api/translators/1/rate-changes",
        dict(safe_rate, source_lang="zh", target_lang="en"), token=AT, headers=safety_headers,
    )
    chk("agent同键业务等价内容返回原待审",
        equivalent_same_key.get("pending_id") == safe_first.get("pending_id")
        and equivalent_same_key.get("deduplicated") is True,
        equivalent_same_key)
    changed_rate = dict(safe_rate, new_rate=772)
    chk("agent同幂等键不同内容409",
        code(lambda: req("POST", "/api/translators/1/rate-changes", changed_rate,
                         token=AT, headers=safety_headers)) == 409)
    equivalent_rate = dict(safe_rate, source_lang=" zh ", target_lang="en")
    _, content_retry = req("POST", "/api/translators/1/rate-changes", equivalent_rate, token=AT,
                           headers={"Idempotency-Key": "acceptance:" + run_tag + ":rate-copy"})
    chk("agent规范化后相同活动内容防重",
        content_retry.get("pending_id") == safe_first.get("pending_id") and content_retry.get("deduplicated") is True,
        content_retry)
    req("POST", f"/api/pending/{safe_first['pending_id']}/reject", token=ET)
    _, safe_resubmit = req("POST", "/api/translators/1/rate-changes", safe_rate, token=AT,
                           headers={"Idempotency-Key": "acceptance:" + run_tag + ":rate-resubmit"})
    chk("已处理内容可用新幂等键重提", safe_resubmit.get("pending_id") != safe_first.get("pending_id"), safe_resubmit)
    req("POST", f"/api/pending/{safe_resubmit['pending_id']}/reject", token=ET)

    _, po_preview = req("POST", "/api/po",
                        {"translator_id": 1, "settlement_month": "2026-10", "role": "翻译", "word_count": 1000},
                        token=AT, headers={"X-Dry-Run": "true"})
    chk("agent PO dry-run不落库",
        po_preview.get("dry_run") is True
        and len(req("GET", "/api/po?month=2026-10")[1]) == 0
        and len(req("GET", "/api/pending", token=ET)[1]) == 0,
        po_preview)
    _, status_preview = req("PUT", "/api/po/1/status", {"status": "已支付"}, token=AT,
                            headers={"X-Dry-Run": "true"})
    po_status_after_preview = next(p["status"] for p in req("GET", "/api/po")[1] if p["id"] == 1)
    chk("agent PO状态dry-run不落库",
        status_preview.get("dry_run") is True and po_status_after_preview == "已开票待付"
        and len(req("GET", "/api/pending", token=ET)[1]) == 0,
        status_preview)
    chk("agent费率dry-run校验语言对",
        code(lambda: req("POST", "/api/translators/1/rate-changes",
                         dict(safe_rate, source_lang="xx", target_lang="KO"), token=AT,
                         headers={"X-Dry-Run": "true"})) == 400)
    chk("agent PO dry-run校验译员",
        code(lambda: req("POST", "/api/po",
                         {"translator_id": 99999, "settlement_month": "2026-10"}, token=AT,
                         headers={"X-Dry-Run": "true"})) == 404)
    chk("agent PO状态dry-run校验目标PO",
        code(lambda: req("PUT", "/api/po/99999/status", {"status": "已支付"}, token=AT,
                         headers={"X-Dry-Run": "true"})) == 404)
    durable_po = {"translator_id": 1, "settlement_month": "2026-12", "role": "翻译",
                  "word_count": 1000, "rate": 180, "po_number": "PO-IDEMPOTENT-" + run_tag}
    durable_headers = {"Idempotency-Key": "acceptance:" + run_tag + ":durable-po"}
    _, durable_pending = req("POST", "/api/po", durable_po, token=AT, headers=durable_headers)
    req("POST", f"/api/pending/{durable_pending['pending_id']}/approve", token=ET)
    try:
        _, durable_retry = req("POST", "/api/po", durable_po, token=AT, headers=durable_headers)
    except urllib.error.HTTPError as exc:
        durable_retry = {"http_error": exc.code}
    chk("已批准PO同键重试返回原结果",
        durable_retry.get("pending_id") == durable_pending.get("pending_id")
        and durable_retry.get("status") == "approved" and durable_retry.get("deduplicated") is True,
        durable_retry)
    chk("已批准PO同键不同请求409",
        code(lambda: req("POST", "/api/po", dict(durable_po, settlement_month="2027-01"),
                         token=AT, headers=durable_headers)) == 409)

    before_agent_rate = [t for t in req("GET", "/api/translators")[1] if t["id"] == 1][0]["translation_rate"]
    _, pr = req("POST", "/api/translators/1/rate-changes", {"change_date": "2026-06-25", "task_type": "翻译", "new_rate": 777}, token=AT)
    chk("agent费率→待审", pr.get("pending") is True)
    chk("待审期间主表未变", [t for t in req("GET", "/api/translators")[1] if t["id"] == 1][0]["translation_rate"] == before_agent_rate)
    req("POST", f"/api/pending/{pr['pending_id']}/reject", token=ET)
    chk("驳回后待审清空", len(req("GET", "/api/pending", token=ET)[1]) == 0)
    req("POST", "/api/translators/1/capacity", {"period_year": 2026, "period_month": 6, "week_no": 2, "project": "agent", "occupancy_pct": 30}, token=AT)
    chk("agent档期直接落", any(w["period"] == "2026-06 W2" for w in req("GET", "/api/translators/1/capacity")[1]["weeks"]))

    print("=== F 优化校验（枚举/唯一性）===")
    chk("非法译员状态422", code(lambda: req("POST", "/api/translators", {"name": "状态X", "status": "乱", "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 422)
    chk("非法入库日期422", code(lambda: req("POST", "/api/translators", {"name": "日期X", "native_language": "中文", "onboarding_date": "2025-01-32"}, token=ET)) == 422)
    chk("非法邮箱422", code(lambda: req("POST", "/api/translators", {"name": "邮箱X", "email": "bad-email", "native_language": "中文", "onboarding_date": "2025-01-01"}, token=ET)) == 422)
    chk("非法PO结算月422", code(lambda: req("POST", "/api/po", {"translator_id": 1, "settlement_month": "2026-13"}, token=ET)) == 422)
    chk("非法产能占用422", code(lambda: req("POST", "/api/translators/1/capacity", {"period_year": 2026, "period_month": 6, "week_no": 1, "occupancy_pct": 101}, token=ET)) == 422)
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
    chk("质量联动 低错累计+3", q3["low_error_count"] == (b3["low_error_count"] or 0) + 3)
    chk("谈判联动 成功后谈后费率", (lambda t: (req("POST", "/api/translators/3/rate-changes", {"change_date": "2026-06-25", "task_type": "翻译", "original_rate": 150, "new_rate": 140, "result": "成功"}, token=ET), tr(3))[1]["post_negotiation_rate"] == 140)(None))

    print("=== H 子表删除 ===")
    _, del_tr = req("POST", "/api/translators", {
        "name": "删除校验" + run_tag,
        "email": f"delete{run_tag}@x.com",
        "native_language": "中文",
        "onboarding_date": "2026-07-01"
    }, token=ET)
    did = del_tr["id"]
    req("POST", f"/api/translators/{did}/language-pairs",
        {"source_lang": "ZH", "target_lang": "KO", "translation_rate": 200}, token=ET)
    lp_id = req("GET", f"/api/translators/{did}/language-pairs")[1][0]["id"]
    req("DELETE", f"/api/translators/{did}/language-pairs/{lp_id}", token=ET)
    chk("删除语言对后列表为空", req("GET", f"/api/translators/{did}/language-pairs")[1] == [])
    req("POST", f"/api/translators/{did}/rate-changes",
        {"change_date": "2026-07-01", "task_type": "翻译", "original_rate": 200, "new_rate": 180, "result": "成功"},
        token=ET)
    rc_id = req("GET", f"/api/translators/{did}/rate-changes")[1][0]["id"]
    req("DELETE", f"/api/translators/{did}/rate-changes/{rc_id}", token=ET)
    chk("删除报价变更后列表为空", req("GET", f"/api/translators/{did}/rate-changes")[1] == [])
    req("POST", f"/api/translators/{did}/quality", {"evaluation_period": "2026-06", "score": 80, "minor_errors": 2}, token=ET)
    req("POST", f"/api/translators/{did}/quality", {"evaluation_period": "2026-07", "score": 100, "minor_errors": 1}, token=ET)
    q_id = req("GET", f"/api/translators/{did}/quality")[1][0]["id"]
    req("DELETE", f"/api/translators/{did}/quality/{q_id}", token=ET)
    dq = tr(did)
    chk("删除质量后重算最近分", dq["recent_qa_score"] == 80 and dq["cumulative_qa_score"] == 80 and dq["low_error_count"] == 2, dq)
    req("POST", f"/api/translators/{did}/contracts", {"contract_number": "DEL-" + run_tag, "status": "有效"}, token=ET)
    ct_id = req("GET", f"/api/translators/{did}/contracts")[1][0]["id"]
    req("DELETE", f"/api/translators/{did}/contracts/{ct_id}", token=ET)
    chk("删除合同后列表为空", req("GET", f"/api/translators/{did}/contracts")[1] == [])
    req("POST", f"/api/translators/{did}/complaints", {"severity": "一般", "deduction_amount": 120}, token=ET)
    cp_id = req("GET", f"/api/translators/{did}/complaints")[1][0]["id"]
    req("DELETE", f"/api/translators/{did}/complaints/{cp_id}", token=ET)
    dc = tr(did)
    chk("删除客诉后重算次数扣款", dc["complaint_count"] == 0 and dc["deduction_total"] == 0, dc)
    req("POST", f"/api/translators/{did}/capacity",
        {"period_year": 2026, "period_month": 7, "week_no": 1, "project": "A", "occupancy_pct": 30},
        token=ET)
    cap_id = req("GET", f"/api/translators/{did}/capacity")[1]["rows"][0]["id"]
    req("DELETE", f"/api/translators/{did}/capacity/{cap_id}", token=ET)
    chk("删除产能后列表为空", req("GET", f"/api/translators/{did}/capacity")[1]["rows"] == [])
    req("PUT", f"/api/translators/{did}/payment",
        {"currency": "CNY", "bank_name": "测试银行", "bank_account": "6222000011112222", "payee_name": "删除校验"},
        token=ET)
    req("DELETE", f"/api/translators/{did}/payment", token=ET)
    chk("删除支付信息后为空", req("GET", f"/api/translators/{did}/payment")[1] is None)
    chk("boss删除子表403", code(lambda: req("DELETE", f"/api/translators/{did}/quality/1", token=BT)) == 403)

    print()
    print("结果:", f"{sum(ok)}/{len(ok)} 全通过 ✅" if all(ok) else f"{sum(ok)}/{len(ok)}（有失败）")
    rc = 0 if all(ok) else 1
    stop_isolated_server()
    return rc


if __name__ == "__main__":
    sys.exit(main())
