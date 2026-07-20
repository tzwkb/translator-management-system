import { getDatabase } from "../../../db";
import { createApproval, ensureDatabase } from "../../../db/repository";
import { errorResponse, json, requireText, roleFromRequest, ValidationError } from "../../../lib/api";
import { assertPermission } from "../../../lib/roles";
import { validateApprovalPayload } from "../../../lib/approvals";
import type { ApprovalKind, Approval } from "../../../lib/types";

export async function POST(request: Request): Promise<Response> {
  try {
    assertPermission(roleFromRequest(request), "submit-approval");
    const body = (await request.json()) as Record<string, unknown>;
    if (body.kind !== "rate" && body.kind !== "po") {
      throw new ValidationError("审核类型必须是费率或 PO");
    }
    const payload = validateApprovalPayload(body.kind, body.payload);
    const approval: Approval = {
      id: `approval-${crypto.randomUUID()}`,
      kind: body.kind as ApprovalKind,
      payload,
      submittedBy: requireText(body.submittedBy ?? "Demo Agent（示例）", "提交人"),
      status: "pending",
      reviewer: null,
      note: null,
      createdAt: new Date().toISOString(),
      reviewedAt: null,
    };
    const db = getDatabase();
    await ensureDatabase(db);
    await createApproval(db, approval);
    return json({ ok: true }, 201);
  } catch (error) {
    return errorResponse(error);
  }
}
