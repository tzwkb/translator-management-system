import { normalizeRole, RolePermissionError } from "./roles";
import type { DemoRole } from "./types";

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

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
  if (error instanceof ValidationError) {
    return json({ error: error.message }, 400);
  }
  const message = error instanceof Error ? error.message : "未知错误";
  return json({ error: message }, 500);
}

export function requireText(
  value: unknown,
  label: string,
  maxLength = 160,
): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new ValidationError(`${label}不能为空`);
  }
  const result = value.trim();
  if (result.length > maxLength) {
    throw new ValidationError(`${label}过长`);
  }
  return result;
}

export function requireInteger(value: unknown, label: string): number {
  if (!Number.isInteger(value) || Number(value) < 0) {
    throw new ValidationError(`${label}必须是非负整数`);
  }
  return Number(value);
}
