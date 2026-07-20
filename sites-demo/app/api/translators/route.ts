import { getDatabase } from "../../../db";
import { createTranslator, ensureDatabase } from "../../../db/repository";
import { errorResponse, json, roleFromRequest } from "../../../lib/api";
import { assertPermission } from "../../../lib/roles";
import { normalizeTranslatorInput } from "../../../lib/validation";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const body = (await request.json()) as Record<string, unknown>;
    const db = getDatabase();
    await ensureDatabase(db);
    await createTranslator(db, {
      id: `tr-${crypto.randomUUID()}`,
      ...normalizeTranslatorInput(body),
    });
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
