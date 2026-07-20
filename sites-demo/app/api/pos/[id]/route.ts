import { getDatabase } from "../../../../db";
import { ensureDatabase, updatePoStatus } from "../../../../db/repository";
import { errorResponse, json, roleFromRequest, ValidationError } from "../../../../lib/api";
import { assertPermission } from "../../../../lib/roles";
import type { PoStatus } from "../../../../lib/types";

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
    if (!["draft", "confirmed", "paid"].includes(String(body.status))) {
      throw new ValidationError("无效的 PO 状态");
    }
    const db = getDatabase();
    await ensureDatabase(db);
    await updatePoStatus(db, params.id, body.status as PoStatus);
    return json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
