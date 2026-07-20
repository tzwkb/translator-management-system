import { getDatabase } from "../../../db";
import { createPurchaseOrder, ensureDatabase } from "../../../db/repository";
import { errorResponse, json, roleFromRequest } from "../../../lib/api";
import { calculateAmountCents } from "../../../lib/money";
import { assertPermission } from "../../../lib/roles";
import { normalizePoInput } from "../../../lib/validation";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const body = (await request.json()) as Record<string, unknown>;
    const input = normalizePoInput(body);
    const db = getDatabase();
    await ensureDatabase(db);
    await createPurchaseOrder(db, {
      id: `po-${crypto.randomUUID()}`,
      ...input,
      amountCents: calculateAmountCents(input.wordCount, input.unitRateMicros),
      createdAt: new Date().toISOString(),
    });
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
