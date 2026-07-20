import { getDatabase } from "../../../db";
import { createPurchaseOrder, ensureDatabase } from "../../../db/repository";
import { errorResponse, json, requireInteger, requireText, roleFromRequest } from "../../../lib/api";
import { calculateAmountCents } from "../../../lib/money";
import { assertPermission } from "../../../lib/roles";
import type { PoStatus } from "../../../lib/types";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const body = (await request.json()) as Record<string, unknown>;
    const wordCount = requireInteger(body.wordCount, "字数");
    const unitRateMicros = requireInteger(body.unitRateMicros, "单价");
    const status: PoStatus = body.status === "confirmed" ? "confirmed" : "draft";
    const db = getDatabase();
    await ensureDatabase(db);
    await createPurchaseOrder(db, {
      id: `po-${crypto.randomUUID()}`,
      poNumber: requireText(body.poNumber, "PO 号"),
      translatorId: requireText(body.translatorId, "译员"),
      month: requireText(body.month, "月份", 7),
      languagePair: requireText(body.languagePair, "语言对"),
      wordCount,
      unitRateMicros,
      amountCents: calculateAmountCents(wordCount, unitRateMicros),
      currency: requireText(body.currency, "币种", 3).toUpperCase(),
      status,
      createdAt: new Date().toISOString(),
    });
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
