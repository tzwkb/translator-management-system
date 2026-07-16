"""translator-mgmt-agent client payload tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import client  # noqa: E402


def main():
    calls = []

    def fake_req(method, path, body=None, token=None, headers=None):
        calls.append((method, path, body, token, headers))
        if path == "/api/login":
            return {"token": "TOKEN", "role": "agent", "name": "资源端Agent"}
        if path == "/api/language-pair-options":
            return [{"source_lang": "ZH", "target_lang": "KO", "label": "ZH→KO"}]
        return {"ok": True}

    original_req = client._req
    client._req = fake_req
    try:
        c = client.Client(base="http://example.invalid")
        c.propose_rate(7, "翻译", 188, source_lang="ZH", target_lang="KO",
                       currency="CNY", original_rate=180, reason="wechat",
                       idempotency_key="wechat:chat-1:msg-9:rate", dry_run=True)
        rate_body = calls[-1][2]
        assert rate_body["source_lang"] == "ZH"
        assert rate_body["target_lang"] == "KO"
        assert rate_body["currency"] == "CNY"
        assert rate_body["original_rate"] == 180
        assert rate_body["new_rate"] == 188
        assert calls[-1][4] == {
            "Idempotency-Key": "wechat:chat-1:msg-9:rate",
            "X-Dry-Run": "true",
        }

        c.propose_po(7, "2026-06", "翻译", 12000, source_lang="ZH",
                     target_lang="KO", project="Game")
        po_body = calls[-1][2]
        assert po_body["word_count"] == 12000
        assert po_body["source_lang"] == "ZH"
        assert po_body["target_lang"] == "KO"
        assert "rate" not in po_body
        assert calls[-1][4] == {}

        c.propose_po_status(12, "已支付", idempotency_key="wecom:chat-2:msg-8:po-status")
        assert calls[-1][0:3] == ("PUT", "/api/po/12/status", {"status": "已支付"})
        assert calls[-1][4] == {"Idempotency-Key": "wecom:chat-2:msg-8:po-status"}

        assert c.language_options() == [{"source_lang": "ZH", "target_lang": "KO", "label": "ZH→KO"}]
    finally:
        client._req = original_req

    print("client payload helpers include language pair fields and safety headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
