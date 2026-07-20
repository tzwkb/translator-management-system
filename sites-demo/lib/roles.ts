import type { DemoRole } from "./types";

export type Permission =
  | "write-business"
  | "submit-approval"
  | "review-approval";

const roles = new Set<DemoRole>(["boss", "editor", "viewer", "agent"]);

const permissions: Record<DemoRole, ReadonlySet<Permission>> = {
  boss: new Set(["write-business", "submit-approval", "review-approval"]),
  editor: new Set(["write-business"]),
  viewer: new Set(),
  agent: new Set(["submit-approval"]),
};

export class RolePermissionError extends Error {
  constructor(
    readonly role: DemoRole,
    readonly permission: Permission,
  ) {
    super(`${role} cannot perform ${permission}`);
    this.name = "RolePermissionError";
  }
}

export function normalizeRole(value: string | null | undefined): DemoRole {
  return roles.has(value as DemoRole) ? (value as DemoRole) : "viewer";
}

export function canPerform(role: DemoRole, permission: Permission): boolean {
  return permissions[role].has(permission);
}

export function assertPermission(
  role: DemoRole,
  permission: Permission,
): void {
  if (!canPerform(role, permission)) {
    throw new RolePermissionError(role, permission);
  }
}
