import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

for (const id of [
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
  assert.match(html, new RegExp(`id="${id}"`), `${id} should exist`);
}

assert.match(html, /PO 组合筛选（全部条件同时满足）/);
assert.match(html, /function applyPOFilters/);
assert.match(html, /function resetPOFilters/);
assert.match(html, /\["translator", filterValue\("poTranslator"\)\]/);
assert.match(html, /\["po_number", filterValue\("poNumber"\)\]/);
assert.match(html, /\["source_lang", filterValue\("poSourceLang"\)\]/);
assert.match(html, /\["target_lang", filterValue\("poTargetLang"\)\]/);
assert.match(html, /\["pricing_mode", filterValue\("poPricingMode"\)\]/);
assert.match(html, /\["settlement_mode", filterValue\("poSettlementMode"\)\]/);
assert.match(html, /\["min_amount", filterValue\("poMinAmount"\)\]/);
assert.match(html, /\["max_amount", filterValue\("poMaxAmount"\)\]/);
assert.match(html, /new URLSearchParams\(\)/);
assert.match(html, /get\(`\/api\/po\/summary\?\$\{params\.toString\(\)\}`\)/);
assert.match(html, /\/api\/po\/price-match/);
assert.match(html, /\/api\/po\/unpaid\/\$\{translatorId\}/);
assert.match(html, /function editPO/);

console.log("PO combined-filter UI is wired");
