import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /id="poImportFile"[^>]+type="file"[^>]+accept="\.xlsx"/);
assert.match(html, /导入 PO Excel/);
assert.match(html, /function importPOFile/);
assert.match(html, /\/api\/import\/po/);
assert.match(html, /skipped_dup_po/);
assert.match(html, /invalid_rows/);

console.log("PO import UI is wired");
