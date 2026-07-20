import { getDatabase } from "../../../db";
import { createTranslator, ensureDatabase } from "../../../db/repository";
import { errorResponse, json, requireText, roleFromRequest } from "../../../lib/api";
import { assertPermission } from "../../../lib/roles";
import type { TranslatorStatus } from "../../../lib/types";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "write-business");
    const body = (await request.json()) as Record<string, unknown>;
    const status = body.status === "inactive" ? "inactive" : "active";
    const db = getDatabase();
    await ensureDatabase(db);
    await createTranslator(db, {
      id: `tr-${crypto.randomUUID()}`,
      name: requireText(body.name, "姓名", 80),
      email: requireText(body.email, "邮箱", 160),
      nativeLanguage: requireText(body.nativeLanguage, "母语", 80),
      status: status as TranslatorStatus,
      onboardedAt: requireText(body.onboardedAt, "入库日期", 10),
    });
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
