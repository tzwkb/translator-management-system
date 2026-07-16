import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

for (const id of ["f-onboarding_date", "f-contract_expiry", "f-last_contact", "a-date", "c-sign", "c-exp", "x-date"]) {
  assert.match(html, new RegExp(`id="${id}"[^>]+type="date"`), `${id} should use date input`);
}

for (const id of ["p-settlement_month", "q-period"]) {
  assert.match(html, new RegExp(`id="${id}"[^>]+type="month"`), `${id} should use month input`);
}

for (const id of ["f-punctuality_rate", "q-score", "cp-occ"]) {
  assert.match(html, new RegExp(`id="${id}"[^>]+min="0"[^>]+max="100"`), `${id} should be limited to 0-100`);
}

for (const id of ["p-word_count", "p-rate", "a-orig", "a-new", "x-ded"]) {
  assert.match(html, new RegExp(`id="${id}"[^>]+min="0"`), `${id} should reject negative values`);
}

assert.match(html, /function isDateValue/);
assert.match(html, /function isMonthValue/);
assert.match(html, /function validRange/);
assert.match(html, /function validateTranslatorForm/);
assert.match(html, /function validatePOForm/);

console.log("field format validation is wired in the UI");
