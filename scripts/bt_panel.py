#!/usr/bin/env python3
"""宝塔面板客户端：登录、读写文件、调用面板接口。

凭据一律通过环境变量提供，代码中不保存任何地址或口令：
    BT_ORIGIN  面板地址，如 https://<面板主机>:<端口>
    BT_ENTRY   安全入口路径，如 /<你的随机入口>
    BT_USER    面板用户名
    BT_PASS    面板密码
"""
import base64
import hashlib
import json
import os
import re
import sys
import time
from http.cookiejar import LWPCookieJar
from pathlib import Path

import requests
import urllib3
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import load_pem_public_key

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

COOKIE_JAR = Path(os.getenv("BT_COOKIE_JAR", "/tmp/bt-panel.cookies"))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def _js_string(html, name):
    m = re.search(r"window\." + name + r"\s*=\s*(['\"`])(.*?)\1", html, re.S)
    if not m:
        raise RuntimeError(f"页面缺少 {name}")
    return m.group(2).replace("\\n", "\n")


class Panel:
    def __init__(self, origin=None, entry=None, user=None, password=None, verify=False):
        self.origin = (origin or os.environ["BT_ORIGIN"]).rstrip("/")
        self.entry = entry or os.environ["BT_ENTRY"]
        self.user = user or os.environ["BT_USER"]
        self.password = password or os.environ["BT_PASS"]
        self.session = requests.Session()
        self.session.verify = verify
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": self.origin + self.entry,
            "Origin": self.origin,
        })
        if COOKIE_JAR.exists():
            self.session.cookies = LWPCookieJar(str(COOKIE_JAR))
            self.session.cookies.load(ignore_discard=True, ignore_expires=True)

    def login(self):
        r = self.session.get(self.origin + self.entry, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"面板入口不可用：HTTP {r.status_code}")
        if "vite_public_login_token" not in r.text:
            if self._adopt_request_token(r.text):
                return "复用已登录会话"
            home = self.session.get(self.origin + "/", timeout=30)
            if home.status_code == 200 and self._adopt_request_token(home.text):
                return "复用已登录会话"
            raise RuntimeError("面板未返回登录页，且已有会话无效")
        html = r.text
        token = _js_string(html, "vite_public_login_token")
        pubkey = load_pem_public_key(_js_string(html, "vite_public_encryption").encode())
        md5 = lambda v: hashlib.md5(v.encode()).hexdigest()
        enc = lambda v: base64.b64encode(pubkey.encrypt(v.encode(), PKCS1v15())).decode()
        form = {
            "username": enc(md5(md5(self.user + token))),
            "password": enc(md5(md5(self.password) + "_bt.cn")),
            "safe_mode": "1",
        }
        r = self.session.post(self.origin + "/login", data=form, timeout=30,
                              allow_redirects=False)
        data = r.json()
        if not isinstance(data, dict) or not data.get("status"):
            raise RuntimeError(f"登录失败：{data}")
        COOKIE_JAR.parent.mkdir(parents=True, exist_ok=True)
        jar = LWPCookieJar(str(COOKIE_JAR))
        for c in self.session.cookies:
            jar.set_cookie(c)
        jar.save(ignore_discard=True, ignore_expires=True)

        home = self.session.get(self.origin + "/", timeout=30)
        self._adopt_request_token(home.text)
        return data.get("msg", "登录成功")

    def _adopt_request_token(self, html):
        m = re.search(r"window\.vite_public_request_token\s*=\s*['\"]([^'\"]+)['\"]",
                      html)
        if not m:
            return False
        self.session.headers["x-http-token"] = m.group(1)
        return True

    def request(self, method, endpoint, **kwargs):
        kwargs.setdefault("timeout", 60)
        r = self.session.request(method, self.origin + endpoint, **kwargs)
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.status_code, r.json()
        return r.status_code, r.text

    def read_file(self, path):
        return self.request("POST", "/files?action=GetFileBody", data={"path": path})

    def write_file(self, path, content):
        return self.request("POST", "/files?action=SaveFileBody",
                            data={"path": path, "data": content, "encoding": "utf-8"})

    def shell(self, cmd, cwd="/tmp", timeout=300, poll=2):
        """经面板执行单行 shell，返回 (exit_code, output)。串行使用，勿并发。"""
        one_line = " ".join(cmd.split())
        marker = hashlib.md5(f"{one_line}{cwd}{time.time()}".encode()).hexdigest()[:12]
        out = f"/tmp/bt-exec-{marker}.log"
        script = (f"cd {cwd}; {{ {one_line} ; }} > {out} 2>&1 ; "
                  f"echo __EXIT_$? >> {out}")
        code, resp = self.request("POST", "/files?action=ExecShell",
                                  data={"path": "/tmp", "shell": script})
        if not isinstance(resp, dict) or not resp.get("status"):
            return None, f"ExecShell 调用失败：{resp}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(poll)
            rc, body = self.read_file(out)
            text = body.get("data", "") if isinstance(body, dict) else (
                body if isinstance(body, str) else "")
            m = re.search(r"__EXIT_(\d+)\s*$", text.rstrip(), re.S)
            if m:
                return int(m.group(1)), re.sub(r"__EXIT_\d+\s*$", "", text).strip()
        return None, "超时未取到结果"

    def ls(self, path, show_row=200):
        return self.request("POST", "/files?action=GetDir",
                            data={"path": path, "p": 1, "showRow": show_row})


def main():
    p = Panel()
    p.login()
    if len(sys.argv) < 2:
        print("已登录")
        return
    cmd = sys.argv[1]
    if cmd == "login":
        print("已登录")
    elif cmd == "call":
        method, endpoint = sys.argv[2], sys.argv[3]
        body = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        code, data = p.request(method, endpoint, json=body)
        print(code)
        print(json.dumps(data, ensure_ascii=False, indent=1) if not isinstance(data, str) else data[:4000])
    elif cmd == "read":
        code, body = p.read_file(sys.argv[2])
        print(code)
        print(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)[:2000])
    elif cmd == "ls":
        code, d = p.ls(sys.argv[2])
        print(code, d.get("PATH") if isinstance(d, dict) else "")
        if isinstance(d, dict):
            for item in d.get("DIR", []) + d.get("FILES", []):
                print("  ", item)
    elif cmd == "write":
        content = Path(sys.argv[3]).read_text()
        print(p.write_file(sys.argv[2], content))
    else:
        raise SystemExit(f"未知命令：{cmd}")


if __name__ == "__main__":
    main()
