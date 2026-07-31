import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

for (const removedId of [
  "poMonth",
  "poTranslator",
  "poProject",
  "poStatus",
  "poRole",
  "poSourceLang",
  "poTargetLang",
  "poCurrency",
  "poPricingMode",
  "poSettlementMode",
  "poMinAmount",
  "poMaxAmount",
  "poNumber",
]) {
  assert.doesNotMatch(html, new RegExp(`id="${removedId}"`), `${removedId} should be removed`);
}

assert.doesNotMatch(html, /PO 组合筛选（全部条件同时满足）/);
assert.doesNotMatch(html, /function applyPOFilters/);
assert.doesNotMatch(html, /function resetPOFilters/);
assert.doesNotMatch(html, /\/api\/po\/summary/);
assert.match(html, /data-excel-field="settlement_mode">结算方式<\/th>/);
assert.match(html, /data-excel-more-grid="po"/);
assert.match(html, /const PO_MORE_FIELDS=/);
assert.match(html, /field:"source_lang"/);
assert.match(html, /field:"target_lang"/);
assert.match(html, /field:"remarks"/);
assert.match(html, /field:"source_key"/);
assert.match(html, /get\("\/api\/po"\)/);
assert.match(html, /get\("\/api\/translators"\)/);
assert.match(html, /PO_ALL_ROWS=allRows\.map/);
assert.match(html, /EXCEL_FILTERS\.po\.settlement_month=\{selected:new Set\(\[latest\]\),condition:null\}/);
assert.match(html, /skipField:"settlement_month"/);
assert.match(html, /function selectedPOMonth/);
assert.match(html, /renderPOGrid\(\)/);
assert.match(html, /\/api\/po\/price-match/);
assert.match(html, /\/api\/po\/unpaid\/\$\{translatorId\}/);
assert.match(html, /function editPO/);

console.log("PO filtering is consolidated into Excel-style headers");
