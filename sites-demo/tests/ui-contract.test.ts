import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("replaces the starter with the Chinese translator operations workbench", async () => {
  const [page, layout, workbench] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/workbench.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(page, /LinguaControlWorkbench/);
  assert.match(layout, /Lingua Control · 译员运营台/);
  assert.match(layout, /lang="zh-CN"/);
  assert.match(layout, /\$\{origin\}\/og\.png/);
  assert.match(workbench, /受控 Demo/);
  assert.match(workbench, /总览/);
  assert.match(workbench, /译员/);
  assert.match(workbench, /费率/);
  assert.match(workbench, /PO/);
  assert.match(workbench, /审核/);
  assert.doesNotMatch(page + layout + workbench, /codex-preview|SkeletonPreview/);
});
