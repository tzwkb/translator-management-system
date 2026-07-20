import { getDatabase } from "../../../../db";
import { ensureDatabase, updateTranslator } from "../../../../db/repository";
import { errorResponse, json, requireText, roleFromRequest } from "../../../../lib/api";
import { assertPermission } from "../../../../lib/roles";
import type { TranslatorStatus } from "../../../../lib/types";

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
    const status = body.status === "inactive" ? "inactive" : "active";
    const db = getDatabase();
    await ensureDatabase(db);
    await updateTranslator(db, {
      id: params.id,
      name: requireText(body.name, "姓名", 80),
      email: requireText(body.email, "邮箱", 160),
      nativeLanguage: requireText(body.nativeLanguage, "母语", 80),
      status: status as TranslatorStatus,
      onboardedAt: requireText(body.onboardedAt, "入库日期", 10),
    });
    return json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
