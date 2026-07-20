import { getDatabase } from "../../../../db";
import { ensureDatabase, updatePoStatus } from "../../../../db/repository";
import { errorResponse, json, roleFromRequest } from "../../../../lib/api";
import { assertPermission } from "../../../../lib/roles";
import { normalizePoStatus } from "../../../../lib/validation";

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
    const status = normalizePoStatus(body.status, true);
    const db = getDatabase();
    await ensureDatabase(db);
    await updatePoStatus(db, params.id, status);
    return json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
