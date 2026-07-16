import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /body:not\(\.viewer\) \.po-status-read \{ display:none !important; \}/);
assert.match(html, /<span class="pill po-status-read st-\$\{p\.status\}">/);
assert.match(html, /<select class="statussel edit-only"/);

console.log("PO status avoids duplicate display in editor mode");
