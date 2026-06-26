"""译员管理系统 API 客户端（给 agent skill 用）。

以 资源端Agent 身份登录，封装常用写操作：
- 档期 set_capacity 直接生效；
- 费率 propose_rate / PO propose_po 进待审队列（系统返回 {"pending": True}）。
绕过本机 Clash 代理直连 localhost。上服务器后改 BASE 即可。
"""
import datetime
import json
import os
import urllib.request

BASE = os.environ.get("TRANSLATOR_API_BASE", "http://127.0.0.1:8000")
_OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕代理


def _req(method, path, body=None, token=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    with _OP.open(req, timeout=10) as resp:
        return json.loads(resp.read().decode() or "null")


class Client:
    def __init__(self, base=None, user="资源端Agent"):
        global BASE
        if base:
            BASE = base
        d = _req("POST", "/api/login", {"user": user})
        self.token = d["token"]
        self.role = d["role"]
        self.name = d["name"]

    # ---- 读 ----
    def translators(self):
        return _req("GET", "/api/translators")

    def find(self, name):
        """按名字找译员（精确或子串匹配），找不到返回 None。"""
        for t in self.translators():
            if t["name"] == name or name in t["name"] or t["name"] in name:
                return t
        return None

    # ---- 写：低风险，直接生效 ----
    def set_capacity(self, tid, year, month, week, project, occupancy_pct):
        return _req("POST", f"/api/translators/{tid}/capacity",
                    {"period_year": year, "period_month": month, "week_no": week,
                     "project": project, "occupancy_pct": occupancy_pct}, self.token)

    # ---- 写：钱相关，进待审（返回 {"pending": True, ...}）----
    def propose_rate(self, tid, task_type, new_rate, reason=None, negotiator=None, change_date=None):
        return _req("POST", f"/api/translators/{tid}/rate-changes",
                    {"change_date": change_date or datetime.date.today().isoformat(),
                     "task_type": task_type, "new_rate": new_rate,
                     "reason": reason, "negotiator": negotiator}, self.token)

    def propose_po(self, tid, settlement_month, role, word_count, rate, currency="CNY", project=None):
        return _req("POST", "/api/po",
                    {"translator_id": tid, "settlement_month": settlement_month, "role": role,
                     "word_count": word_count, "rate": rate, "currency": currency,
                     "project": project}, self.token)


if __name__ == "__main__":
    c = Client()
    print("登录:", c.name, c.role)
    print("译员数:", len(c.translators()))
