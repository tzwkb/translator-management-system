import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.doesNotMatch(html, /字数\(千\)/);
assert.match(html, /data-excel-field="pricing_mode">计价<\/th>/);
assert.match(html, /data-excel-field="word_count">数量<\/th>/);
assert.match(html, /data-excel-field="rate">单价<\/th>/);
assert.match(html, /id="p-quantity-label">字数（字）/);
assert.match(html, /id="p-rate-label">单价（\/千字）/);
assert.match(html, /per_1000:"金额 = 字数 ÷ 1000 × 单价/);
assert.match(html, /per_hour:"金额 = 小时数 × 小时单价/);
assert.match(html, /fixed:"一口价直接使用固定总额/);
assert.match(html, /manual:"手工金额用于明确的结算调整/);

console.log("PO pricing labels follow the selected pricing mode");
