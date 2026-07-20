import { normalizeRole, RolePermissionError } from "./roles";
import type { DemoRole } from "./types";
import { DomainError } from "./errors";
import { normalizedSafeInteger, normalizedText } from "./validation";

export { ValidationError } from "./errors";

export function roleFromRequest(request: Request): DemoRole {
  return normalizeRole(request.headers.get("x-demo-role"));
}

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

export function errorResponse(error: unknown): Response {
  if (error instanceof RolePermissionError) {
    return json({ error: "当前 Demo 角色无权执行此操作" }, 403);
  }
  if (error instanceof DomainError) {
    return json({ error: error.message }, error.status);
  }
  if (error instanceof SyntaxError) {
    return json({ error: "请求 JSON 无效" }, 400);
  }
  console.error("Lingua Control unexpected request error", error);
  return json({ error: "服务器内部错误" }, 500);
}

export function requireText(
  value: unknown,
  label: string,
  maxLength = 160,
): string {
  return normalizedText(value, label, maxLength);
}

export function requireInteger(value: unknown, label: string): number {
  return normalizedSafeInteger(value, label, Number.MAX_SAFE_INTEGER);
}
