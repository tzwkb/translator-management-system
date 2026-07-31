import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

for (const id of [
  "fs-source",
  "fs-target",
  "fs-native",
  "fs-rate",
  "fs-min",
  "fs-max",
  "fs-currency",
  "fs-domain",
  "fs-wechat",
  "fs-rating",
  "fs-gender",
  "fs-entity",
  "fs-availability",
]) {
  assert.match(html, new RegExp(`id="${id}"`), `${id} should exist`);
}
assert.match(html, /function applyPreciseFilters/);
assert.match(html, /function exportFiltered/);
assert.match(html, /URLSearchParams/);

assert.match(html, /\["prices","项目价格"\]/);
assert.match(html, /\["payment","支付账户"\]/);
assert.match(html, /\["attachments","资质附件"\]/);
assert.match(html, /\/project-prices/);
assert.match(html, /\/payment-accounts/);
assert.match(html, /\/attachments/);
assert.match(html, /function editPaymentAccount/);
assert.match(html, /function togglePaymentFields/);
assert.match(html, /api\(id\?"PUT":"POST",`\/api\/translators\/\$\{CUR\.id\}\/payment-accounts/);
assert.match(html, /function downloadPaymentQR/);
assert.match(html, /function downloadAttachment/);
assert.match(html, /personal_bank/);
assert.match(html, /corporate_cny/);
assert.match(html, /corporate_usd/);
assert.match(html, /wechat/);
assert.match(html, /alipay/);

assert.match(html, /\/api\/import\/po\?preview=true/);
assert.match(html, /cumulative_unpaid_by_currency/);
assert.match(html, /computed_availability/);
assert.match(html, /availability_conflict/);
assert.match(html, /质量等级（LQE 均分\/人工）/);
assert.match(html, /id="f-internal_rating" disabled/);
assert.match(html, /id="f-manual_rating"/);
assert.match(html, /id="f-manual_rating_reason"/);
assert.match(html, /id="f-settlement_mode"/);
assert.match(html, /\/api\/translator-filter-fields/);
assert.match(html, /function addGenericFilter/);
assert.match(html, /GENERIC_FILTERS\.length\)params\.set\("filters"/);
assert.match(html, /monthly_capacity/);
assert.match(html, /&lt;50% 空闲；50%–&lt;80% 健康；80%–100% 饱和；&gt;100% 警告/);

console.log("all feedback-requirement UI entry points are wired");
