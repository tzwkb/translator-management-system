"""Hermes 桥 ↔ 译员管理系统 交互契约测试（确定性子集 A/C/D/E/F）。

测的是已集成进 Hermes 的 translator-mgmt-agent skill 的 client.py
（经 HERMES_HOME 软链导入，验证集成产物本身）。
editor 操作用原始 urllib（以 资源端 登录）补全人工复核闭环。
B/H（消息抽取、端到端）与 G（VM 打包）需交互式 Hermes + VM，不在此脚本。
"""
import json
import os
import sys
import urllib.error
import urllib.request

WS = "/Users/spellbook/Desktop/Langlobal/langlobal-agents-workshop"
os.environ.setdefault("HERMES_HOME", WS + "/userdata-dev/resource")
os.environ.setdefault("TRANSLATOR_API_BASE", "http://127.0.0.1:8000")
sys.path.insert(0, os.environ["HERMES_HOME"] + "/skills/translator-mgmt-agent")
from client import BASE, Client  # noqa: E402  集成进 Hermes 的那份

OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ed(m, p, body=None, token=None):
    h = {}
    if token:
        h["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + p, data=data, method=m, headers=h)
    with OP.open(r, timeout=8) as x:
        return x.status, json.loads(x.read().decode() or "null")


def code(fn):
    try:
        fn()
        return "no-error"
    except urllib.error.HTTPError as e:
        return e.code


ok = []


def chk(n, c, extra=""):
    ok.append(bool(c))
    print(("✓" if c else "✗ 失败:"), n, extra)


_, edu = ed("POST", "/api/login", {"user": "资源端"})
ET = edu["token"]

print("=== A 连通与鉴权 ===")
print("  BASE =", BASE, "| HERMES_HOME =", os.environ["HERMES_HOME"])
c = Client()
chk("A2 agent登录(role=agent)", c.role == "agent" and c.name == "资源端Agent")
chk("A1 系统可达 overview 200", ed("GET", "/api/overview")[0] == 200)
zhang = c.find("张明")
tid = zhang["id"]

print("=== C 档期直接生效 ===")
chk("C1 set_capacity ok", c.set_capacity(tid, 2026, 6, 4, "烟云", 100).get("ok") is True)
caps = ed("GET", f"/api/translators/{tid}/capacity")[1]
chk("C2 档期落库可见", any(w["period"] == "2026-06 W4" for w in caps["weeks"]))

print("=== D 费率/PO 进待审 ===")
rate0 = c.find("张明")["translation_rate"]
pr = c.propose_rate(tid, "翻译", 260, source_lang="ZH", target_lang="EN",
                    currency="CNY", reason="微信里译员要求")
chk("D1 费率→pending", pr.get("pending") is True)
chk("D2 待审期间主表未变", c.find("张明")["translation_rate"] == rate0)
ppo = c.propose_po(tid, "2026-07", "翻译", 8000, source_lang="ZH", target_lang="EN")
chk("D3 PO→pending", ppo.get("pending") is True)
chk("D4 待审队列可见≥2", len(ed("GET", "/api/pending", token=ET)[1]) >= 2)

print("=== E 护栏与安全 ===")
chk("E1 agent不能批准403", code(lambda: ed("POST", f"/api/pending/{pr['pending_id']}/approve", token=c.token)) == 403)
chk("E2 agent不能建译员403", code(lambda: ed("POST", "/api/translators", {"name": "X", "native_language": "中", "onboarding_date": "2026-01-01"}, token=c.token)) == 403)
chk("E3 agent不能加客诉403", code(lambda: ed("POST", f"/api/translators/{tid}/complaints", {"severity": "一般"}, token=c.token)) == 403)
chk("E5 钱一律pending(无直落路径)", c.propose_rate(tid, "翻译", 300, source_lang="ZH", target_lang="EN").get("pending") is True)

print("=== F 人工复核闭环 ===")
ed("POST", f"/api/pending/{pr['pending_id']}/approve", token=ET)
lps = c.language_pairs(tid)
chk("F1 批准后ZH→EN语言对费率=260",
    any(lp["source_lang"] == "ZH" and lp["target_lang"] == "EN" and lp["translation_rate"] == 260 for lp in lps))
ed("POST", f"/api/pending/{ppo['pending_id']}/approve", token=ET)
pos = ed("GET", "/api/po?month=2026-07")[1]
chk("F3 批准后PO落库", any(p["translator_id"] == tid and p["word_count"] == 8000 for p in pos))
for pc in ed("GET", "/api/pending", token=ET)[1]:
    ed("POST", f"/api/pending/{pc['id']}/reject", token=ET)
chk("F2 驳回后待审清空", len(ed("GET", "/api/pending", token=ET)[1]) == 0)
acts = {a["action"] for a in ed("GET", "/api/audit", token=ET)[1]}
chk("F4 审计含提交/批准/驳回", {"提交建议", "批准", "驳回"} <= acts)

print()
print("结果:", f"{sum(ok)}/{len(ok)} 通过 ✅" if all(ok) else f"{sum(ok)}/{len(ok)}（有失败）")
sys.exit(0 if all(ok) else 1)
