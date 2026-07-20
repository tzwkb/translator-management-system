import { getDatabase } from "../../../../db";
import { ensureDatabase, reviewApproval } from "../../../../db/repository";
import { errorResponse, json, requireText, roleFromRequest, ValidationError } from "../../../../lib/api";
import { assertPermission } from "../../../../lib/roles";

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "review-approval");
    const [body, params] = await Promise.all([
      request.json() as Promise<Record<string, unknown>>,
      context.params,
    ]);
    if (body.status !== "approved" && body.status !== "rejected") {
      throw new ValidationError("审核结果无效");
    }
    const db = getDatabase();
    await ensureDatabase(db);
    await reviewApproval(
      db,
      params.id,
      body.status,
      "Demo Boss（示例）",
      requireText(body.note ?? (body.status === "approved" ? "批准" : "驳回"), "审核意见"),
    );
    return json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
