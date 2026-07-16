import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

const modalSections = [
  ["editMask", "<!-- 新增/编辑译员 -->", "<!-- 译员详情"],
  ["detailMask", "<!-- 译员详情", "<!-- 新增 PO -->"],
  ["poMask", "<!-- 新增 PO -->", "<script>"],
];

function section(startMarker, endMarker) {
  const start = html.indexOf(startMarker);
  const end = html.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(start, -1, `${startMarker} exists`);
  assert.notEqual(end, -1, `${endMarker} exists after ${startMarker}`);
  return html.slice(start, end);
}

for (const [maskId, startMarker, endMarker] of modalSections) {
  const part = section(startMarker, endMarker);
  assert.match(part, new RegExp(`class="modal-close"[^>]+onclick="closeModal\\('${maskId}'\\)"`));
  assert.match(part, /aria-label="关闭弹窗"/);
}

const modalCloseRule = html.match(/\.modal-close\s*\{([^}]+)\}/)?.[1] || "";
assert.match(modalCloseRule, /position:\s*fixed/, "close button stays pinned while modal content scrolls");
assert.doesNotMatch(modalCloseRule, /position:\s*absolute/, "close button must not scroll with modal content");
assert.match(modalCloseRule, /top:\s*calc\(5vh \+ 9px\)/, "close button top tracks modal top");
assert.match(modalCloseRule, /right:\s*calc\(\(100vw - var\(--modal-box-width\)\) \/ 2 \+ 12px\)/, "close button right edge tracks modal width");

console.log("modal close buttons stay pinned");
