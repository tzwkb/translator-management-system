import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

for (const field of [
  "name",
  "entity_type",
  "gender",
  "language_pairs",
  "status",
  "internal_rating",
  "current_project",
  "effective_availability",
  "contract_expiry",
  "last_contact",
]) {
  assert.match(
    html,
    new RegExp(`data-excel-grid="tr" data-excel-field="${field}"`),
    `translator column ${field} should expose an Excel-style filter`,
  );
}

for (const field of [
  "translator_name",
  "settlement_month",
  "project",
  "language_pair",
  "role",
  "pricing_mode",
  "word_count",
  "rate",
  "amount",
  "currency",
  "status",
  "po_number",
  "settlement_mode",
]) {
  assert.match(
    html,
    new RegExp(`data-excel-grid="po" data-excel-field="${field}"`),
    `PO column ${field} should expose an Excel-style filter`,
  );
}

for (const token of [
  'id="excelFilterMenu"',
  'id="excelMoreMenu"',
  'id="excelValueSearch"',
  'id="excelSelectAll"',
  'id="excelConditionOp"',
  'id="excelConditionInputs"',
  'id="excelMoreSearch"',
  'id="excelMoreField"',
  "function openExcelFilter",
  "function openExcelMore",
  "function toggleExcelSelectAll",
  "function applyExcelCurrentField",
  "function addExcelMoreFilter",
  "function applyTranslatorMoreFilters",
  "function setExcelSort",
  "function applyExcelState",
  "function matchesExcelCondition",
  "function repositionExcelFilter",
  "function renderExcelFilterBar",
  "function clearExcelFilters",
  "EXCEL_FILTERS={tr:{},po:{}}",
  "MORE_FILTERS={tr:[],po:[]}",
  "EXCEL_SORT={tr:null,po:null}",
]) {
  assert.match(html, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}

assert.match(html, /表头筛选 · 更多字段可筛选未展示信息/);
assert.match(html, /全选当前结果/);
assert.match(html, /data-excel-key/);
assert.match(html, /data-excel-more-grid="tr"/);
assert.match(html, /data-excel-more-grid="po"/);
assert.match(html, /state\.selected\.has\(raw\)/);
assert.match(html, /matchesExcelCondition\(raw,state\.condition,def\)/);
assert.match(html, /apply\.disabled=!EXCEL_MENU_STATE\.selected\.size/);
assert.match(html, /focus\(\{preventScroll:true\}\)/);
assert.match(html, /leftKey===EXCEL_BLANK&&rightKey!==EXCEL_BLANK/);
assert.match(html, /applyExcelState\("tr",translatorSearchRows\(\)\)/);
assert.match(html, /applyExcelState\("po",baseRows\)/);
assert.match(html, /computePOSummary\(list,cumulativeRows\)/);
assert.match(html, /skipField:"settlement_month"/);
assert.match(html, /最多添加 20 条/);
assert.match(html, /filters",JSON\.stringify\(MORE_FILTERS\.tr\)/);
assert.match(html, /\.excel-filter-trigger\.active/);
assert.match(html, /\.excel-filter-menu/);
assert.doesNotMatch(html, /精确组合筛选（全部条件同时满足）/);
assert.doesNotMatch(html, /PO 组合筛选（全部条件同时满足）/);

console.log("Unified Excel-style column and more-field filters are wired");
