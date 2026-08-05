import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /data-excel-grid="tr" data-excel-field="id">(?:译员)?唯一编号<\/th>/);
assert.match(html, /id:\{label:"唯一编号",kind:"number",value:row=>row\.id\}/);
assert.match(html, /<td class="num translator-id">\$\{t\.id\}<\/td>/);
assert.match(html, /const columns = \["id","name"/);
assert.match(html, /String\(row\.id\)/, "home search should accept a translator ID");
assert.match(html, /<span class="chip">唯一编号 \$\{CUR\.id\}<\/span>/);

assert.doesNotMatch(html, /<select id="p-translator_id"/);
assert.match(html, /<input id="p-translator_id" type="hidden">/);
assert.match(html, /id="p-translator_name"[^>]+role="combobox"[^>]+aria-autocomplete="list"/);
assert.match(html, /id="p-translator-menu"[^>]+role="listbox"/);
assert.match(html, /function poTranslators\(\) \{\s*return PO_TRANSLATORS\.length \? PO_TRANSLATORS : DATA;/);
for (const functionName of [
  "openTranslatorMenu",
  "toggleTranslatorMenu",
  "translatorInputChanged",
  "commitTranslatorInput",
  "pickTranslator",
  "closeTranslatorMenu",
  "setPOTranslator",
]) {
  assert.match(html, new RegExp(`function ${functionName}`));
}
assert.match(html, /姓名或唯一编号/);
assert.match(html, /唯一编号 \$\{t\.id\}/);
assert.match(html, /请从联想结果中选择译员/);
assert.match(html, /无匹配译员/);
assert.match(html, /function translatorMatches\(query\) \{[\s\S]*?String\(t\.id\)\.includes\(q\)[\s\S]*?t\.name/);
assert.match(html, /function translatorInputChanged\(\) \{\s*document\.getElementById\("p-translator_id"\)\.value="";/);
assert.match(html, /function commitTranslatorInput\(\) \{[\s\S]*?String\(t\.id\)===query[\s\S]*?exact\.length===1\)pickTranslator/);
assert.match(html, /selected\.value=translator\?\.id\?\?"";/);
assert.match(html, /input\.setAttribute\("aria-expanded","true"\);/);
assert.match(html, /input\?\.setAttribute\("aria-expanded","false"\);/);
assert.match(html, /function openPO\(\) \{\s*setPOTranslator\(null\);/);
assert.match(html, /function editPO\(id\) \{[\s\S]*?setPOTranslator\(p\.translator_id\);/);
assert.match(html, /function pickTranslator\(id\) \{[\s\S]*?fillPORate\(\);/);
assert.match(html, /const tid = Number\(document\.getElementById\("p-translator_id"\)\.value\);/);
assert.match(html, /translator_id:Number\(document\.getElementById\("p-translator_id"\)\.value\)/);
assert.match(html, /function translatorKeydown\(event\) \{[\s\S]*?event\.key==="ArrowDown"[\s\S]*?event\.key==="Enter"/);
assert.match(html, /if \(!e\.target\.closest\("\.translator-combo"\)\) closeTranslatorMenu\(\);/);
assert.match(html, /document\.addEventListener\("scroll", positionTranslatorMenu, true\);/);
assert.match(html, /window\.addEventListener\("resize", \(\) => \{[\s\S]*?positionTranslatorMenu\(\);/);

console.log("PO translator autocomplete and visible translator IDs are wired");
