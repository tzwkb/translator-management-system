import assert from "node:assert/strict";
import test from "node:test";
import {
  assertPermission,
  canPerform,
  normalizeRole,
} from "../lib/roles";
import { canReviewApproval, validateApprovalPayload } from "../lib/approvals";
import { calculateAmountCents, parseRateMicros } from "../lib/money";

test("normalizes unknown roles to viewer", () => {
  assert.equal(normalizeRole("owner"), "viewer");
  assert.equal(normalizeRole(undefined), "viewer");
});

test("keeps role write permissions aligned with the demo policy", () => {
  assert.equal(canPerform("boss", "write-business"), true);
  assert.equal(canPerform("boss", "review-approval"), true);
  assert.equal(canPerform("editor", "write-business"), true);
  assert.equal(canPerform("editor", "review-approval"), false);
  assert.equal(canPerform("agent", "submit-approval"), true);
  assert.equal(canPerform("agent", "write-business"), false);
  assert.equal(canPerform("viewer", "write-business"), false);
  assert.throws(
    () => assertPermission("editor", "review-approval"),
    /editor.*review-approval/i,
  );
});

test("allows only boss to resolve a pending approval", () => {
  assert.equal(canReviewApproval("pending", "approved", "boss"), true);
  assert.equal(canReviewApproval("pending", "rejected", "boss"), true);
  assert.equal(canReviewApproval("pending", "approved", "editor"), false);
  assert.equal(canReviewApproval("approved", "rejected", "boss"), false);
});

test("rejects incomplete approval payloads before they enter the queue", () => {
  assert.throws(
    () => validateApprovalPayload("rate", { translatorId: "tr-1" }),
    /费率提案不完整/,
  );
  assert.throws(
    () => validateApprovalPayload("po", { poNumber: "PO-1", wordCount: -1 }),
    /PO 提案不完整/,
  );
});

test("calculates PO amount in cents from a decimal per-word rate", () => {
  const rateMicros = parseRateMicros("0.1285");
  assert.equal(rateMicros, 128_500);
  assert.equal(calculateAmountCents(12_345, rateMicros), 158_633);
});

test("rejects invalid money inputs", () => {
  assert.throws(() => parseRateMicros("-0.1"), /rate/i);
  assert.throws(() => calculateAmountCents(-1, 100_000), /word count/i);
});
