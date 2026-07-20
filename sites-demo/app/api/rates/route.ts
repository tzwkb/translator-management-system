import { getDatabase } from "../../../db";
import { ensureDatabase, upsertRate } from "../../../db/repository";
import { errorResponse, json, requireInteger, requireText, roleFromRequest } from "../../../lib/api";
import { assertPermission } from "../../../lib/roles";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const body = (await request.json()) as Record<string, unknown>;
    const db = getDatabase();
    await ensureDatabase(db);
    await upsertRate(db, {
      id: `rate-${crypto.randomUUID()}`,
      translatorId: requireText(body.translatorId, "译员"),
      languagePair: requireText(body.languagePair, "语言对"),
      rateMicros: requireInteger(body.rateMicros, "费率"),
      currency: requireText(body.currency, "币种", 3).toUpperCase(),
      updatedAt: new Date().toISOString(),
    });
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
