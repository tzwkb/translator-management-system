import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.doesNotMatch(html, /字数\(千\)/);
assert.match(html, /<th>字数（字）<\/th>/);
assert.match(html, /<th>单价（\/千字）<\/th>/);
assert.match(html, /金额 = 字数（字）÷ 1000 × 单价（\/千字）/);

console.log("PO word count label uses actual-character unit");
