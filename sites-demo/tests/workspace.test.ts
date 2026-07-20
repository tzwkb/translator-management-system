import assert from "node:assert/strict";
import test from "node:test";
import { summarizePendingAmounts } from "../db/repository";
import { formatApprovalSummary } from "../lib/approval-display";
import type { Approval, PurchaseOrder, Translator } from "../lib/types";

const translators: Translator[] = [
  {
    id: "tr-1",
    name: "林夏",
    email: "linxia@example.test",
    nativeLanguage: "简体中文",
    status: "active",
    onboardedAt: "2026-01-08",
  },
];

test("summarizes unpaid PO amounts separately by currency", () => {
  const base: Omit<PurchaseOrder, "id" | "currency" | "amountCents" | "status"> = {
    poNumber: "PO-1",
    translatorId: "tr-1",
    month: "2026-07",
    languagePair: "en-US → zh-CN",
    wordCount: 100,
    unitRateMicros: 100_000,
    createdAt: "2026-07-20T00:00:00.000Z",
  };
  const rows: PurchaseOrder[] = [
    { ...base, id: "po-1", currency: "CNY", amountCents: 1_000, status: "draft" },
    { ...base, id: "po-2", currency: "USD", amountCents: 2_500, status: "confirmed" },
    { ...base, id: "po-3", currency: "CNY", amountCents: 3_000, status: "paid" },
  ];
  assert.deepEqual(summarizePendingAmounts(rows), [
    { currency: "CNY", amountCents: 1_000 },
    { currency: "USD", amountCents: 2_500 },
  ]);
});

test("PO approval summary shows every persisted field and server amount", () => {
  const approval: Approval = {
    id: "approval-1",
    kind: "po",
    payload: {
      poNumber: "PO-1",
      translatorId: "tr-1",
      month: "2026-07",
      languagePair: "en-US → zh-CN",
      wordCount: 1_000,
      unitRateMicros: 120_000,
      currency: "CNY",
      status: "draft",
    },
    submittedBy: "Demo Agent",
    status: "pending",
    reviewer: null,
    note: null,
    createdAt: "2026-07-20T00:00:00.000Z",
    reviewedAt: null,
  };
  assert.equal(
    formatApprovalSummary(approval, translators),
    "PO-1 · 林夏 · 2026-07 · en-US → zh-CN · 1,000 字 · 0.12 CNY/字 · ¥120.00 · 草稿",
  );
});
