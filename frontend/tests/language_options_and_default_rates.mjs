import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const services = fs.readFileSync(new URL("../../backend/app/services.py", import.meta.url), "utf8");
const admin = fs.readFileSync(new URL("../../backend/app/routers/admin.py", import.meta.url), "utf8");

const languageLine = services.match(/LANGUAGE_OPTIONS = \[(.*?)\]/s)?.[1] || "";
const languages = [...languageLine.matchAll(/"([^"]+)"/g)].map((m) => m[1]);

assert.ok(languages.length >= 80, `expected at least 80 languages, got ${languages.length}`);
for (const code of ["ZH", "ZH-HANS", "ZH-HANT", "EN", "EN-US", "EN-GB", "JA", "KO", "FR", "FR-CA", "DE", "ES", "ES-LA", "PT-BR", "RU", "TH", "VI", "ID", "AR", "TR", "UK", "HI", "HE", "FA", "SW"]) {
  assert.ok(languages.includes(code), `${code} should be selectable`);
}

assert.doesNotMatch(html, /<datalist id="languageOptions">/, "native datalist is not reliable enough for the language picker");
assert.match(html, /function langInputHtml[\s\S]+class="lang-combo"/);
assert.match(html, /function openLangMenu/);
assert.match(html, /function toggleLangMenu/);
assert.match(html, /function pickLang/);
assert.match(html, /function closeLangMenus/);
assert.match(html, /role="listbox"/);
assert.match(html, /role="option"/);
for (const id of ["el-src", "el-tgt", "la-src", "la-tgt", "a-src", "a-tgt", "p-source_lang", "p-target_lang"]) {
  const staticInput = new RegExp(`<input id="${id}"[^>]+class="lang-input"`).test(html);
  const generatedInput = html.includes(`langInputHtml("${id}"`);
  const staticMenu = new RegExp(`id="${id}-menu"[^>]+role="listbox"`).test(html);
  assert.ok(staticInput || generatedInput, `${id} should be a filterable language input`);
  assert.ok(staticMenu || generatedInput, `${id} should have an expandable option menu`);
  assert.doesNotMatch(html, new RegExp(`<select id="${id}"`));
}

assert.doesNotMatch(html, /默认(?:翻译| MTPE|审校| LQA)?费率/);
assert.doesNotMatch(html, /默认翻译费率/);
assert.doesNotMatch(html, /id="f-(?:translation_rate|mtpe_rate|review_rate|lqa_rate)"/);
assert.doesNotMatch(admin, /"translation_rate"/);
assert.doesNotMatch(admin, /"mtpe_rate"/);
assert.doesNotMatch(admin, /"review_rate"/);
assert.doesNotMatch(admin, /"lqa_rate"/);

console.log("language options expanded, searchable menus open, and default rate UI removed");
