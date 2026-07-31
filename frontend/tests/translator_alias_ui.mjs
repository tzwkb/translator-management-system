import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /\["aliases","名称映射"\]/);
assert.match(html, /function subAliases/);
assert.match(html, /function addAlias/);
assert.match(html, /function editAlias/);
assert.match(html, /\/aliases/);
assert.match(html, /同 ID 覆盖/);

console.log("translator alias and same-ID import UI is wired");
