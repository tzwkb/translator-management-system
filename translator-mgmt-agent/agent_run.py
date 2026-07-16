"""B+H 实跑：扮演 Hermes agent，读样例消息→抽取→按护栏决策→调真桥写真系统→报告→闭环。

抽取/决策由 agent（Claude）给出，执行打真实系统。消息为受控样例（可复现），
覆盖：档期(直接落)、语言对费率(待审)、PO(待审)、新译员(无权·交人)、玩笑(存疑·交人)。
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import BASE, Client  # noqa: E402

_OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ed(m, p, body=None, token=None):
    h = {}
    if token:
        h["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + p, data=data, method=m, headers=h)
    with _OP.open(r, timeout=8) as x:
        return x.status, json.loads(x.read().decode() or "null")


c = Client()
print("agent 登录:", c.name, c.role, "| 系统:", BASE, "\n")

# ---- 读到的样例消息（B 的输入）----
msgs = [
    ("张明", "烟云这边我下周第3周排满了，第4周才有空"),
    ("李娜", "这个月价能不能从 220 涨到 240？最近接的活多"),
    ("王伟", "诺诺项目 6 月我做了大概 12 千字"),
    ("资源群", "推荐个做韩语的新译员小赵，ZH→KO，想合作"),
    ("陈静", "哈哈我想涨到一个亿"),
]

direct, pending, human = [], [], []
print("=== agent 逐条抽取与决策 ===")
for who, text in msgs:
    print(f"[{who}] {text}")

    if who == "张明":
        z = c.find("张明")
        c.set_capacity(z["id"], 2026, 6, 3, "烟云", 100)
        msg = "→ 档期：2026-06 第3周 烟云 占用100% —— 直接落库"
        direct.append("张明 2026-06 W3 烟云 占用100%")

    elif who == "李娜":
        l = c.find("李娜")
        r = c.propose_rate(l["id"], "翻译", 240, original_rate=220,
                           source_lang="ZH", target_lang="JA", currency="CNY",
                           reason="微信：活多，要求 ZH→JA 翻译 220→240")
        msg = f"→ 费率：ZH→JA 翻译 220→240（钱相关）—— 进待审 #{r['pending_id']}"
        pending.append(f"李娜 ZH→JA 翻译费率 220→240  #{r['pending_id']}")

    elif who == "王伟":
        w = c.find("王伟")
        r = c.propose_po(w["id"], "2026-06", "翻译", 12000,
                         source_lang="ZH", target_lang="EN", project="诺诺")
        msg = f"→ PO：2026-06 诺诺 ZH→EN 12000字（钱相关）—— 进待审 #{r['pending_id']}"
        pending.append(f"王伟 PO 2026-06 诺诺 ZH→EN 12000字  #{r['pending_id']}")

    elif who == "资源群":
        try:
            ed("POST", "/api/translators",
               {"name": "小赵", "native_language": "中文", "onboarding_date": "2026-06-26",
                "language_pairs": "ZH→KO"}, token=c.token)
            msg = "→ 新译员：竟然落库了？（不应发生）"
            human.append("新译员 小赵（异常落库）")
        except urllib.error.HTTPError as e:
            msg = f"→ 新译员：agent 无建档权（{e.code}）—— 转资源端处理"
            human.append("新译员 小赵 ZH→KO —— 资源端建档")

    else:  # 陈静
        msg = "→ 『涨到一个亿』疑似玩笑/数字不实 —— 不写，待核实"
        human.append("陈静『涨到一个亿』—— 存疑待核实")

    print("   " + msg + "\n")

print("=== 【agent 自动同步报告】 ===")
print(f"✅ 已自动更新档期 {len(direct)} 条：" + "".join("\n   · " + x for x in direct))
print(f"⏳ 待人工审核 {len(pending)} 条（费率/PO）：" + "".join("\n   · " + x for x in pending))
print(f"🙋 需人工处理 {len(human)} 条：" + "".join("\n   · " + x for x in human))

# ---- H 闭环：editor 批准其中一条费率待审 → 对应语言对费率更新 ----
_, edu = ed("POST", "/api/login", {"user": "资源端"})
ET = edu["token"]
pend_list = ed("GET", "/api/pending", token=ET)[1]
rate_pc = next(p for p in pend_list if p["kind"] == "rate_change")
before = c.language_pairs(c.find("李娜")["id"])
ed("POST", f"/api/pending/{rate_pc['id']}/approve", token=ET)
after = c.language_pairs(c.find("李娜")["id"])
print(f"\n=== 【人工复核闭环】 ===")
print(f"editor 批准李娜费率待审：语言对费率 {before} → {after}")
print(f"剩余待审 {len(ed('GET', '/api/pending', token=ET)[1])} 条（王伟 PO 仍候审，符合预期）")
