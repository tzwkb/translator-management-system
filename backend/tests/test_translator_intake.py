"""在临时数据库上验证内部管理与独立公开入口；不会连接业务数据库。"""
import copy
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import test_acceptance as api

BACKEND = Path(__file__).resolve().parents[1]
PUBLIC_BASE = ""
EDITOR = ""
PASSED = 0


def check(label, condition):
    global PASSED
    assert condition, label
    PASSED += 1
    print(f"PASS {label}")


def public(method="GET", body=None, token=None, path="/api/public/intake", raw=None, content_type="application/json"):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = "Invite " + token
    data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(PUBLIC_BASE + path, data=data, method=method, headers=headers)
    with api.OP.open(request, timeout=8) as response:
        value = response.read()
        if "json" in response.headers.get("content-type", ""):
            value = json.loads(value)
        return response.status, value, response.headers


def staff(method, path, body=None):
    return api.req(method, "/api/intake" + path, body, token=EDITOR)[1]


def translator_profile(translator_id):
    return next(row for row in api.req("GET", "/api/translators")[1] if row["id"] == translator_id)


def invite(email, translator_id=None):
    body = {"email": email}
    if translator_id:
        body["translator_id"] = translator_id
    row = staff("POST", "/invites", body)
    return row, row["url"].rsplit("#", 1)[1]


def payload(email="intake-new@example.com", name="自填专项新译员"):
    return {"name": name, "email": email, "native_language": "中文", "gender": "female",
            "entity_type": "individual", "daily_output": 4000, "consent": True,
            "language_pairs": [{"source_lang": "ZH", "target_lang": "EN", "translation_rate": 230.5,
                                "review_rate": 120, "currency": "CNY"}],
            "projects": [{"project_name": "自填专项项目", "cooperation_source": "external", "project_status": "past",
                          "source_lang": "ZH", "target_lang": "EN", "role": "翻译", "start_date": "2026-01-01"}]}


def review(submission_id, action="approve", **overrides):
    target_id = overrides.get("target_id")
    detail = staff("GET", f"/submissions/{submission_id}" + (f"?target_id={target_id}" if target_id else ""))
    body = {"action": action, "version": detail["version"], "target_id": detail["target_id"],
            "profile_fingerprint": detail["profile_fingerprint"], "onboarding_date": "2026-09-07"}
    body.update(overrides)
    return staff("POST", f"/submissions/{submission_id}/review", body)


def sql(statement, args=()):
    with sqlite3.connect(Path(api.TMPDIR.name) / "acceptance.db") as connection:
        return connection.execute(statement, args).fetchall()


def wait_ready(base, path):
    for _ in range(60):
        try:
            with api.OP.open(base + path, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"隔离服务未能启动: {base}")


def main():
    global PUBLIC_BASE, EDITOR
    if os.getenv("BASE"):
        raise RuntimeError("自填专项必须使用临时数据库；请移除 BASE。")
    public_port = api.free_port()
    PUBLIC_BASE = f"http://127.0.0.1:{public_port}"
    os.environ["INTAKE_PUBLIC_BASE_URL"] = PUBLIC_BASE
    api.start_isolated_server()
    public_server = None
    try:
        wait_ready(api.BASE, "/api/overview")
        env = os.environ.copy()
        env.update(DB_URL=f"sqlite:///{Path(api.TMPDIR.name) / 'acceptance.db'}", AES_KEY="0" * 64)
        public_server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.intake_public:app", "--host", "127.0.0.1",
                                          "--port", str(public_port), "--no-access-log"], cwd=BACKEND, env=env,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_ready(PUBLIC_BASE, "/intake")
        EDITOR = api.req("POST", "/api/login", {"user": "资源端"})[1]["token"]
        viewer = api.req("POST", "/api/login", {"user": "boss"})[1]["token"]
        agent = api.req("POST", "/api/login", {"user": "资源端Agent"})[1]["token"]
        for unauthorized in (None, viewer, agent):
            for method, path, body in (("GET", "/invites", None), ("GET", "/submissions", None),
                                       ("POST", "/invites", {"email": "denied@example.com"}),
                                       ("GET", "/submissions/1", None), ("POST", "/invites/1/revoke", {}),
                                       ("POST", "/submissions/1/review", {"action": "approve", "version": 1})):
                assert api.code(lambda: api.req(method, "/api/intake" + path, body, token=unauthorized)) == 403
        check("资料管理仅允许资源端/财务编辑角色", True)
        for path in ("/", "/api/login", "/api/translators", "/api/export/translators", "/api/intake/invites", "/docs", "/openapi.json", "/intake-admin.js", "/intake-assets/admin.js"):
            assert api.code(lambda: public(path=path)) == 404, path
        check("独立公开服务无后台、登录、导出或接口文档路由", True)
        page = public(path="/intake")
        check("表单安全响应头、脚本及样式可用", page[0] == 200 and page[2]["Cache-Control"] == "no-store"
              and page[2]["Referrer-Policy"] == "no-referrer" and "frame-ancestors 'none'" in page[2]["Content-Security-Policy"]
              and public(path="/intake-assets/public.js")[0] == public(path="/intake-assets/public.css")[0] == 200)
        check("缺失或伪造邀请无法读取", api.code(lambda: public()) == 404 and api.code(lambda: public(token="x" * 43)) == 404)
        count_before = sql("SELECT count(*) FROM translators")[0][0]
        invitation, token = invite("  INTAKE-NEW@example.com  ")
        context = public(token=token)[1]
        check("邮箱规范化、14天邀请、原令牌只返回一次", context["email"] == "intake-new@example.com" and invitation["preview_only"]
              and invitation["url"].startswith(PUBLIC_BASE + "/intake#") and len(token) == 43
              and token not in json.dumps(staff("GET", "/invites"))
              and token not in str(sql("SELECT token_hash FROM translator_intake_invites")))
        check("邀请上下文不暴露正式档案或内部评级", set(context) == {"email", "expires_at", "is_update", "languages", "submission"})
        data = payload()
        invalid_bodies = [dict(data, email="someone-else@example.com"), dict(data, name="  "), dict(data, status="Active"),
                          dict(data, manual_rating="S"), dict(data, consent=False), dict(data, daily_output=-1),
                          dict(data, language_pairs=[]), dict(data, language_pairs=data["language_pairs"] * 2),
                          dict(data, projects=[{"project_name": "当前项目", "project_status": "current", "cooperation_source": "external"}])]
        for body in invalid_bodies:
            assert api.code(lambda: public("POST", body, token)) in {400, 422}, body
        for rate in (-1, float("nan"), float("inf")):
            body = copy.deepcopy(data)
            body["language_pairs"][0]["translation_rate"] = rate
            assert api.code(lambda: public("POST", body, token)) == 422
        for pair in ({"source_lang": "ZZ", "target_lang": "EN"}, {"source_lang": "EN", "target_lang": "EN"},
                     {"source_lang": "ZH", "target_lang": "EN", "translation_rate": 23},
                     {"source_lang": "ZH", "target_lang": "EN", "rate_confirmed_date": "2026-01-01"}):
            assert api.code(lambda: public("POST", dict(data, language_pairs=[pair]), token)) == 422
        check("必填、邮箱绑定、内部字段、同语种、重复语言对、无穷费率和项目排期校验", True)
        check("大请求与表单跨站直接提交受限", api.code(lambda: public("POST", token=token, raw=b"x" * 131073)) == 413
              and api.code(lambda: public("POST", token=token, raw=b"{}", content_type="text/plain")) == 415)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: public("POST", data, token)[1], range(2)))
        submission_id = results[0]["id"]
        check("并发重复提交只生成一份待审资料", results[0] == results[1] and results[0]["status"] == "pending"
              and sql("SELECT count(*) FROM translators")[0][0] == count_before)
        check("已提交内容不可直接改写", api.code(lambda: public("POST", dict(data, name="修改"), token)) == 409)
        check("待审公开回执不回传完整资料", "draft" not in public(token=token)[1])
        review(submission_id, "needs_info", note="请补充微信 / Please add WeChat")
        reopened = public(token=token)[1]
        check("退回后原链接可读取自己的待补充草稿", reopened["draft"]["name"] == data["name"] and reopened["submission"]["status"] == "needs_info")
        data["wechat"] = "intake-test"
        resubmitted = public("POST", data, token)[1]
        check("补充后保留申请ID并递增版本", resubmitted["id"] == submission_id and resubmitted["version"] == 2)
        check("旧版本审核被拒绝", api.code(lambda: review(submission_id, version=1)) == 409)
        with ThreadPoolExecutor(max_workers=2) as pool:
            approved = list(pool.map(lambda _: review(submission_id, include_rates=True), range(2)))
        translator_id = approved[0]["translator_id"]
        check("并发重复审核仅建档一次", approved[0] == approved[1] and approved[0]["status"] == "approved"
              and sql("SELECT count(*) FROM translators")[0][0] == count_before + 1)
        profile = translator_profile(translator_id)
        check("确认后的基础资料、日期和内部初始状态入库", profile["wechat"] == "intake-test"
              and profile["source"] == "译员自填链接" and profile["status"] == "Probation" and profile["onboarding_date"] == "2026-09-07")
        pairs = api.req("GET", f"/api/translators/{translator_id}/language-pairs")[1]
        check("单独确认报价后写入语言对和项目", pairs[0]["translation_rate"] == 230.5 and pairs[0]["currency"] == "CNY"
              and sql("SELECT count(*) FROM translator_project_experiences WHERE translator_id=?", (translator_id,))[0][0] == 1)
        check("已入库申请不能退回或改写", api.code(lambda: review(submission_id, "needs_info", note="再补充")) == 409)
        _, update_token = invite(data["email"], translator_id)
        check("更新邀请不会向公开页预填内部档案", "draft" not in public(token=update_token)[1])
        updated = payload(name="自填专项更名")
        updated["wechat"] = "  "
        updated["language_pairs"][0]["translation_rate"] = 999
        update_id = public("POST", updated, update_token)[1]["id"]
        detail = staff("GET", f"/submissions/{update_id}")
        sql("UPDATE translators SET location='并行编辑' WHERE id=?", (translator_id,))
        check("后台并行编辑后旧差异不能直接批准", api.code(lambda: review(update_id, profile_fingerprint=detail["profile_fingerprint"])) == 409)
        review(update_id)
        current = translator_profile(translator_id)
        current_pairs = api.req("GET", f"/api/translators/{translator_id}/language-pairs")[1]
        check("更新空白保留旧值、未勾选费率不改报价、同项目不重复新增", current["wechat"] == "intake-test"
              and current["location"] == "并行编辑" and current["status"] == "Probation" and current_pairs[0]["translation_rate"] == 230.5
              and sql("SELECT count(*) FROM translator_project_experiences WHERE translator_id=?", (translator_id,))[0][0] == 1)
        check("更名保留旧名称映射", bool(sql("SELECT id FROM translator_aliases WHERE translator_id=? AND alias=?", (translator_id, data["name"]))))
        _, duplicate_token = invite(data["email"])
        duplicate_id = public("POST", updated, duplicate_token)[1]["id"]
        duplicate_detail = staff("GET", f"/submissions/{duplicate_id}")
        check("重复邮箱申请提示候选并禁止自动新建", any(c["id"] == translator_id for c in duplicate_detail["candidates"])
              and api.code(lambda: review(duplicate_id)) == 409)
        check("不能任意合并其他译员", api.code(lambda: review(duplicate_id, target_id=999999)) == 409)
        review(duplicate_id, target_id=translator_id)
        check("人工选择后可合并，不增加译员数", sql("SELECT count(*) FROM translators")[0][0] == count_before + 1)
        _, currency_token = invite(data["email"], translator_id)
        currency_data = copy.deepcopy(updated)
        currency_data["language_pairs"] = [{"source_lang": "ZH", "target_lang": "EN", "translation_rate": 50, "currency": "USD"}]
        currency_id = public("POST", currency_data, currency_token)[1]["id"]
        check("部分报价不能把旧费率错误换成另一币种", api.code(lambda: review(currency_id, include_rates=True)) == 409
              and sql("SELECT currency FROM language_pairs WHERE translator_id=?", (translator_id,))[0][0] == "CNY")
        check("失败审核整体回滚且保持待审", staff("GET", f"/submissions/{currency_id}")["status"] == "pending")
        review(currency_id, "reject", note="请核对币种")
        check("拒绝不改变正式资料，公开回执显示处理意见", public(token=currency_token)[1]["submission"]["review_note"] == "请核对币种")
        expired, expired_token = invite("expired@example.com")
        sql("UPDATE translator_intake_invites SET expires_at='2000-01-01 00:00:00' WHERE id=?", (expired["id"],))
        check("过期链接不能读取或提交", api.code(lambda: public(token=expired_token)) == 410
              and api.code(lambda: public("POST", payload("expired@example.com"), expired_token)) == 410)
        revoked, revoked_token = invite("revoked@example.com")
        revoked_id = public("POST", payload("revoked@example.com", "待撤销译员"), revoked_token)[1]["id"]
        staff("POST", f"/invites/{revoked['id']}/revoke", {})
        check("撤销阻止后续提交和待审入库", api.code(lambda: public(token=revoked_token)) == 410
              and api.code(lambda: review(revoked_id)) == 409)
        late, late_token = invite("late-review@example.com")
        late_id = public("POST", payload("late-review@example.com", "提交后过期译员"), late_token)[1]["id"]
        sql("UPDATE translator_intake_invites SET expires_at='2000-01-01 00:00:00' WHERE id=?", (late["id"],))
        check("有效期内已提交的资料允许到期后人工审核", review(late_id)["status"] == "approved")
        statuses = []
        for _ in range(125):
            try:
                statuses.append(public(token=token)[0])
            except urllib.error.HTTPError as exc:
                statuses.append(exc.code)
                if exc.code == 429:
                    assert exc.headers["Retry-After"] == "60"
                    break
        check("公开接口有限流并提供重试时间", 429 in statuses)
        check("邀请、提交、审核、撤销均有审计记录", {row[0] for row in sql("SELECT DISTINCT action FROM audit_logs WHERE entity IN ('资料邀请','资料申请')")} >= {"创建", "提交", "审核", "撤销"})
        print(f"Translator intake: {PASSED}/{PASSED} checks passed")
    finally:
        if public_server:
            public_server.terminate()
            public_server.wait(timeout=5)
        api.stop_isolated_server()


if __name__ == "__main__":
    main()
