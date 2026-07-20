import { getDatabase } from "../../../db";
import { ensureDatabase, upsertRate } from "../../../db/repository";
import { errorResponse, json, roleFromRequest } from "../../../lib/api";
import { assertPermission } from "../../../lib/roles";
import { normalizeRateInput } from "../../../lib/validation";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const body = (await request.json()) as Record<string, unknown>;
    const input = normalizeRateInput(body);
    const db = getDatabase();
    await ensureDatabase(db);
    await upsertRate(db, {
      id: `rate-${crypto.randomUUID()}`,
      ...input,
      updatedAt: new Date().toISOString(),
    });
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
