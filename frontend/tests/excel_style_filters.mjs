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
  "availability",
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
]) {
  assert.match(
    html,
    new RegExp(`data-excel-grid="po" data-excel-field="${field}"`),
    `PO column ${field} should expose an Excel-style filter`,
  );
}

for (const token of [
  'id="excelFilterMenu"',
  'id="excelValueSearch"',
  'id="excelSelectAll"',
  "function openExcelFilter",
  "function toggleExcelSelectAll",
  "function applyExcelCurrentField",
  "function setExcelSort",
  "function applyExcelState",
  "function repositionExcelFilter",
  "function renderExcelFilterBar",
  "function clearExcelFilters",
  "EXCEL_FILTERS={tr:{},po:{}}",
  "EXCEL_SORT={tr:null,po:null}",
]) {
  assert.match(html, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}

assert.match(html, /点击表头箭头筛选与排序/);
assert.match(html, /全选当前结果/);
assert.match(html, /data-excel-key/);
assert.match(html, /selected\.has\(excelRawValue/);
assert.match(html, /document\.getElementById\("excelApply"\)\.disabled=!selected\.size/);
assert.match(html, /focus\(\{preventScroll:true\}\)/);
assert.match(html, /leftKey===EXCEL_BLANK&&rightKey!==EXCEL_BLANK/);
assert.match(html, /applyExcelState\("tr",translatorSearchRows\(\)\)/);
assert.match(html, /applyExcelState\("po",baseRows\)/);
assert.match(html, /computePOSummary\(list,allFiltered\)/);
assert.match(html, /\.excel-filter-trigger\.active/);
assert.match(html, /\.excel-filter-menu/);

console.log("Excel-style column filters are wired for translator and PO grids");
