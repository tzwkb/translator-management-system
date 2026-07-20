import { ValidationError } from "./api";
import type {
  ApprovalKind,
  ApprovalStatus,
  DemoRole,
  PoProposal,
  RateProposal,
} from "./types";
import { canPerform } from "./roles";

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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function hasText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function hasNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0;
}

export function validateApprovalPayload(
  kind: ApprovalKind,
  value: unknown,
): RateProposal | PoProposal {
  if (!isRecord(value)) {
    throw new ValidationError(kind === "rate" ? "费率提案不完整" : "PO 提案不完整");
  }

  if (kind === "rate") {
    if (
      !hasText(value.translatorId) ||
      !hasText(value.languagePair) ||
      !hasNonNegativeInteger(value.rateMicros) ||
      !hasText(value.currency)
    ) {
      throw new ValidationError("费率提案不完整");
    }
    return value as RateProposal;
  }

  if (
    !hasText(value.poNumber) ||
    !hasText(value.translatorId) ||
    !hasText(value.month) ||
    !hasText(value.languagePair) ||
    !hasNonNegativeInteger(value.wordCount) ||
    !hasNonNegativeInteger(value.unitRateMicros) ||
    !hasText(value.currency) ||
    !["draft", "confirmed", "paid"].includes(String(value.status))
  ) {
    throw new ValidationError("PO 提案不完整");
  }
  return value as PoProposal;
}
