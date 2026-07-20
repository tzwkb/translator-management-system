import type {
  ApprovalKind,
  ApprovalStatus,
  DemoRole,
  PoProposal,
  RateProposal,
} from "./types";
import { canPerform } from "./roles";
import { normalizePoInput, normalizeRateInput } from "./validation";

export function canReviewApproval(
  current: ApprovalStatus,
  next: ApprovalStatus,
  role: DemoRole,
): boolean {
  return (
    current === "pending" &&
    (next === "approved" || next === "rejected") &&
    canPerform(role, "review-approval")
  );
}

export function validateApprovalPayload(
  kind: ApprovalKind,
  value: unknown,
): RateProposal | PoProposal {
  return kind === "rate" ? normalizeRateInput(value) : normalizePoInput(value);
}
