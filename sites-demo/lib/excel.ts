import { strToU8, zipSync } from "fflate";
import { formatCurrency } from "./money";
import { sanitizeXml10Text } from "./validation";
import type { PurchaseOrder, Translator } from "./types";

export type ExportSheet = {
  name: string;
  rows: Array<Array<string | number>>;
};

export function buildExportSheets(
  translators: Translator[],
  purchaseOrders: PurchaseOrder[],
): ExportSheet[] {
  const names = new Map(translators.map((item) => [item.id, item.name]));
  return [
    {
      name: "译员",
      rows: [
        ["姓名", "邮箱", "母语", "状态", "入库日期"],
        ...translators.map((item) => [
          item.name,
          item.email,
          item.nativeLanguage,
          item.status === "active" ? "在库" : "停用",
          item.onboardedAt,
        ]),
      ],
    },
    {
      name: "PO",
      rows: [
        ["PO 号", "译员", "月份", "语言对", "字数", "单价", "状态", "金额"],
        ...purchaseOrders.map((item) => [
          item.poNumber,
          names.get(item.translatorId) ?? "未找到译员（示例）",
          item.month,
          item.languagePair,
          item.wordCount,
          (item.unitRateMicros / 1_000_000).toFixed(4),
          item.status,
          formatCurrency(item.amountCents, item.currency),
        ]),
      ],
    },
  ];
}

function xmlEscape(value: string | number): string {
  return sanitizeXml10Text(String(value))
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function columnName(index: number): string {
  let result = "";
  let current = index + 1;
  while (current > 0) {
    current -= 1;
    result = String.fromCharCode(65 + (current % 26)) + result;
    current = Math.floor(current / 26);
  }
  return result;
}

function sheetXml(rows: ExportSheet["rows"]): string {
  const body = rows
    .map(
      (row, rowIndex) =>
        `<row r="${rowIndex + 1}">${row
          .map((cell, columnIndex) => {
            const reference = `${columnName(columnIndex)}${rowIndex + 1}`;
            if (typeof cell === "number") {
              return `<c r="${reference}"><v>${cell}</v></c>`;
            }
            return `<c r="${reference}" t="inlineStr"><is><t xml:space="preserve">${xmlEscape(cell)}</t></is></c>`;
          })
          .join("")}</row>`,
    )
    .join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`;
}

export function createXlsx(sheets: ExportSheet[]): Uint8Array {
  const contentTypes = sheets
    .map(
      (_, index) =>
        `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`,
    )
    .join("");
  const workbookSheets = sheets
    .map(
      (sheet, index) =>
        `<sheet name="${xmlEscape(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`,
    )
    .join("");
  const workbookRels = sheets
    .map(
      (_, index) =>
        `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`,
    )
    .join("");

  const files: Record<string, Uint8Array> = {
    "[Content_Types].xml": strToU8(
      `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${contentTypes}</Types>`,
    ),
    "_rels/.rels": strToU8(
      '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    ),
    "xl/workbook.xml": strToU8(
      `<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${workbookSheets}</sheets></workbook>`,
    ),
    "xl/_rels/workbook.xml.rels": strToU8(
      `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${workbookRels}</Relationships>`,
    ),
  };

  sheets.forEach((sheet, index) => {
    files[`xl/worksheets/sheet${index + 1}.xml`] = strToU8(sheetXml(sheet.rows));
  });

  return zipSync(files, { level: 6 });
}
