"""VM 端测试：在 Windows VM 内跑真桥 client.py，打宿主上的系统。
覆盖 A3(跨机登录) / G3(跨机读写) / G2(中文往返) / C1(档期直接) / D1(费率待审)。
用法: python vm_test.py http://<宿主IP>:8000
仅 ASCII 状态输出，避免 Win 控制台 GBK 乱码；中文只做数据层比对。
"""
import json
import os
import sys
import urllib.request

os.environ["TRANSLATOR_API_BASE"] = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import BASE, Client  # noqa: E402  真桥

_OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(p):
    with _OP.open(BASE + p, timeout=10) as x:
        return json.loads(x.read().decode())


ok = []


def chk(n, c):
    ok.append(bool(c))
    print(("PASS" if c else "FAIL"), n)


print("BASE", BASE)
c = Client()
chk("A3 VM->host login role=agent", c.role == "agent" and c.name == "资源端Agent")
ts = c.translators()
chk("G3 cross-machine list>0", len(ts) > 0)
z = c.find("张明")  # 张明
tid = z["id"]
proj = "烟云VM测"  # 烟云VM测（中文，测往返）
chk("C1 capacity direct ok", c.set_capacity(tid, 2026, 6, 5, proj, 50).get("ok") is True)
caps = get("/api/translators/%d/capacity" % tid)
chk("G2 chinese round-trip", any(r.get("project") == proj for r in caps["rows"]))
pr = c.propose_rate(tid, "翻译", 188)  # 翻译
chk("D1 rate->pending from VM", pr.get("pending") is True)
print("RESULT %d/%d" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
