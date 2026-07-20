import { getDatabase } from "../../../../db";
import { ensureDatabase, updateTranslator } from "../../../../db/repository";
import { errorResponse, json, roleFromRequest } from "../../../../lib/api";
import { assertPermission } from "../../../../lib/roles";
import { normalizeTranslatorInput } from "../../../../lib/validation";

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const [body, params] = await Promise.all([
      request.json() as Promise<Record<string, unknown>>,
      context.params,
    ]);
    const db = getDatabase();
    await ensureDatabase(db);
    await updateTranslator(db, {
      id: params.id,
      ...normalizeTranslatorInput(body),
    });
    return json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
