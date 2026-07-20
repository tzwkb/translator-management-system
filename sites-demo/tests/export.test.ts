import assert from "node:assert/strict";
import test from "node:test";
import { unzipSync, strFromU8 } from "fflate";
import { XMLParser, XMLValidator } from "fast-xml-parser";
import { buildExportSheets, createXlsx } from "../lib/excel";

const translators = [
  {
    id: "tr-1",
    name: "林夏",
    email: "linxia@example.test",
    nativeLanguage: "简体中文",
    status: "active" as const,
    onboardedAt: "2026-01-08",
  },
];

const purchaseOrders = [
  {
    id: "po-1",
    poNumber: "PO-DEMO-001",
    translatorId: "missing",
    month: "2026-07",
    languagePair: "en-US → zh-CN",
    wordCount: 1_000,
    unitRateMicros: 120_000,
    amountCents: 12_000,
    currency: "CNY",
    status: "draft" as const,
    createdAt: "2026-07-20T00:00:00.000Z",
  },
];

test("maps current translators and PO rows into two export sheets", () => {
  const sheets = buildExportSheets(translators, purchaseOrders);
  assert.equal(sheets.length, 2);
  assert.deepEqual(sheets[0].rows[1], [
    "林夏",
    "linxia@example.test",
    "简体中文",
    "在库",
    "2026-01-08",
  ]);
  assert.equal(sheets[1].rows[1][1], "未找到译员（示例）");
  assert.equal(sheets[1].rows[1][7], "¥120.00");
});

test("creates a standards-based xlsx zip with both worksheets", () => {
  const bytes = createXlsx(buildExportSheets(translators, purchaseOrders));
  assert.equal(String.fromCharCode(bytes[0], bytes[1]), "PK");

  const files = unzipSync(bytes);
  assert.ok(files["[Content_Types].xml"]);
  assert.ok(files["xl/workbook.xml"]);
  assert.ok(files["xl/worksheets/sheet1.xml"]);
  assert.ok(files["xl/worksheets/sheet2.xml"]);
  assert.match(strFromU8(files["xl/workbook.xml"]), /译员/);
  assert.match(strFromU8(files["xl/workbook.xml"]), /PO/);
});

test("unzipped worksheet XML remains parseable with legacy control characters", () => {
  const legacyTranslators = [
    { ...translators[0], name: "林\u0001夏" },
  ];
  const files = unzipSync(
    createXlsx(buildExportSheets(legacyTranslators, purchaseOrders)),
  );
  const worksheetXml = strFromU8(files["xl/worksheets/sheet1.xml"]);

  assert.equal(XMLValidator.validate(worksheetXml), true);
  const parsed = new XMLParser({ ignoreAttributes: false }).parse(worksheetXml);
  assert.ok(parsed.worksheet.sheetData.row);
  assert.doesNotMatch(worksheetXml, /\u0001/u);
});
