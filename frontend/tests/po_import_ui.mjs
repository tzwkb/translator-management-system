import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /id="poImportFile"[^>]+type="file"[^>]+accept="\.xlsx"/);
assert.match(html, /导入标准 PO Excel/);
assert.match(html, /id="projectlistPOState"/);
assert.match(html, /只读预览 Projectlist/);
assert.match(html, /function previewProjectlistFile/);
assert.match(html, /function renderProjectlistPreview/);
assert.match(html, /projectlist_po_state=/);
assert.match(html, /数量规则待确认/);
assert.match(html, /function importPOFile/);
assert.match(html, /\/api\/import\/po/);
assert.match(html, /skipped_dup_po/);
assert.match(html, /invalid_rows/);

console.log("PO import UI is wired");
