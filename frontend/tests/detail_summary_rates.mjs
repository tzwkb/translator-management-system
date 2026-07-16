import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const script = html
  .match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/\ndocument\.getElementById\("search"\).*?\nswitchRole\(\);\s*\/\/.*?\n/s, "\n");

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id,
      value: "",
      textContent: "",
      innerHTML: "",
      style: {},
      classList: { add() {}, remove() {}, toggle() {} },
      addEventListener() {},
    });
  }
  return elements.get(id);
}

const context = {
  console,
  setTimeout,
  clearTimeout,
  document: {
    body: { classList: { add() {}, remove() {}, toggle() {} } },
    createElement: () => ({
      className: "",
      textContent: "",
      classList: { add() {} },
      remove() {},
    }),
    getElementById: element,
    querySelectorAll: () => [],
  },
  fetch: async (path) => ({
    json: async () => {
      if (path === "/api/translators/1/language-pairs") {
        return [
          { source_lang: "ZH", target_lang: "EN", translation_rate: 180, mtpe_rate: 120, review_rate: 90, currency: "CNY" },
          { source_lang: "ZH", target_lang: "JA", translation_rate: 210, mtpe_rate: 140, review_rate: 100, currency: "CNY" },
        ];
      }
      return [];
    },
  }),
};

vm.createContext(context);
vm.runInContext(script, context);
vm.runInContext(`
DATA = [{
  id: 1,
  name: "测试译员",
  status: "Active",
  language_pairs: "ZH→EN, ZH→JA",
  translation_rate: 180,
  mtpe_rate: 120,
  review_rate: 90,
  currency: "CNY"
}];
LANG_OPTIONS = ["ZH", "EN", "JA"];
`, context);

await context.openDetail(1);
await new Promise((resolve) => setTimeout(resolve, 0));

const summary = element("dSummary").innerHTML;
assert.match(summary, /ZH→JA/);
assert.match(summary, /210/);
assert.match(summary, /140/);
assert.match(summary, /100/);

console.log("detail summary shows per-language-pair rates");
