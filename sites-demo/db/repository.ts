import { calculateAmountCents } from "../lib/money";
import {
  ConflictError,
  DomainError,
  NotFoundError,
  UnprocessableEntityError,
  ValidationError,
} from "../lib/errors";
import { validateApprovalPayload } from "../lib/approvals";
import type {
  Approval,
  ApprovalStatus,
  PoProposal,
  PoStatus,
  PurchaseOrder,
  Rate,
  RateProposal,
  Translator,
  WorkspaceData,
} from "../lib/types";
import {
  mapApprovalRow,
  mapPoRow,
  mapRateRow,
  mapTranslatorRow,
} from "./mappers";

export interface D1StatementLike {
  bind(...values: unknown[]): D1StatementLike;
  first<T>(): Promise<T | null>;
  all<T>(): Promise<{ results: T[] }>;
  run(): Promise<D1ResultLike>;
}

export type D1ResultLike = { meta?: { changes?: number } };

export interface D1DatabaseLike {
  prepare(sql: string): D1StatementLike;
  batch(statements: D1StatementLike[]): Promise<D1ResultLike[]>;
}

const schemaStatements = [
  `CREATE TABLE IF NOT EXISTS translators (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    native_language TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
    onboarded_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS rates (
    id TEXT PRIMARY KEY,
    translator_id TEXT NOT NULL REFERENCES translators(id),
    language_pair TEXT NOT NULL,
    rate_micros INTEGER NOT NULL CHECK (rate_micros BETWEEN 0 AND 100000000),
    currency TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(translator_id, language_pair)
  )`,
  `CREATE TABLE IF NOT EXISTS purchase_orders (
    id TEXT PRIMARY KEY,
    po_number TEXT NOT NULL UNIQUE,
    translator_id TEXT NOT NULL REFERENCES translators(id),
    month TEXT NOT NULL,
    language_pair TEXT NOT NULL,
    word_count INTEGER NOT NULL CHECK (word_count BETWEEN 0 AND 100000000),
    unit_rate_micros INTEGER NOT NULL CHECK (unit_rate_micros BETWEEN 0 AND 100000000),
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    currency TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'confirmed', 'paid')),
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('rate', 'po')),
    payload_json TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    review_token TEXT UNIQUE
  )`,
  "CREATE INDEX IF NOT EXISTS purchase_orders_status_idx ON purchase_orders(status)",
  "CREATE INDEX IF NOT EXISTS approvals_status_idx ON approvals(status)",
];

const seedStatements: Array<{ sql: string; values: unknown[] }> = [
  {
    sql: "INSERT OR IGNORE INTO translators (id, name, email, native_language, status, onboarded_at) VALUES (?, ?, ?, ?, ?, ?)",
    values: ["tr-demo-1", "林夏（示例）", "linxia@example.test", "简体中文", "active", "2026-01-08"],
  },
  {
    sql: "INSERT OR IGNORE INTO translators (id, name, email, native_language, status, onboarded_at) VALUES (?, ?, ?, ?, ?, ?)",
    values: ["tr-demo-2", "Alex Morgan（示例）", "alex@example.test", "English", "active", "2026-03-17"],
  },
  {
    sql: "INSERT OR IGNORE INTO translators (id, name, email, native_language, status, onboarded_at) VALUES (?, ?, ?, ?, ?, ?)",
    values: ["tr-demo-3", "佐藤凛（示例）", "rin@example.test", "日本语", "inactive", "2025-11-22"],
  },
  {
    sql: "INSERT OR IGNORE INTO rates (id, translator_id, language_pair, rate_micros, currency, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
    values: ["rate-demo-1", "tr-demo-1", "en-US → zh-CN", 128_500, "CNY", "2026-07-15T08:30:00.000Z"],
  },
  {
    sql: "INSERT OR IGNORE INTO rates (id, translator_id, language_pair, rate_micros, currency, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
    values: ["rate-demo-2", "tr-demo-2", "zh-CN → en-US", 350_000, "CNY", "2026-07-12T09:10:00.000Z"],
  },
  {
    sql: "INSERT OR IGNORE INTO purchase_orders (id, po_number, translator_id, month, language_pair, word_count, unit_rate_micros, amount_cents, currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    values: ["po-demo-1", "PO-DEMO-260701", "tr-demo-1", "2026-07", "en-US → zh-CN", 12_345, 128_500, 158_633, "CNY", "confirmed", "2026-07-16T02:00:00.000Z"],
  },
  {
    sql: "INSERT OR IGNORE INTO purchase_orders (id, po_number, translator_id, month, language_pair, word_count, unit_rate_micros, amount_cents, currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    values: ["po-demo-2", "PO-DEMO-260702", "tr-demo-2", "2026-07", "zh-CN → en-US", 8_400, 350_000, 294_000, "CNY", "draft", "2026-07-18T04:20:00.000Z"],
  },
  {
    sql: "INSERT OR IGNORE INTO approvals (id, kind, payload_json, submitted_by, status, reviewer, note, created_at, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    values: [
      "approval-demo-1",
      "rate",
      JSON.stringify({ translatorId: "tr-demo-1", languagePair: "ja-JP → zh-CN", rateMicros: 145_000, currency: "CNY" }),
      "Demo Agent（示例）",
      "pending",
      null,
      null,
      "2026-07-19T07:15:00.000Z",
      null,
    ],
  },
];

export async function ensureDatabase(db: D1DatabaseLike): Promise<void> {
  await db.batch(schemaStatements.map((sql) => db.prepare(sql)));
  await db.batch(
    seedStatements.map(({ sql, values }) => db.prepare(sql).bind(...values)),
  );
}

export async function loadWorkspace(db: D1DatabaseLike): Promise<WorkspaceData> {
  await ensureDatabase(db);
  const [translatorRows, rateRows, poRows, approvalRows] = await Promise.all([
    db.prepare("SELECT * FROM translators ORDER BY name").all<Record<string, unknown>>(),
    db.prepare("SELECT * FROM rates ORDER BY updated_at DESC").all<Record<string, unknown>>(),
    db.prepare("SELECT * FROM purchase_orders ORDER BY created_at DESC").all<Record<string, unknown>>(),
    db.prepare("SELECT * FROM approvals ORDER BY created_at DESC").all<Record<string, unknown>>(),
  ]);

  const translators = translatorRows.results.map(mapTranslatorRow);
  const rates = rateRows.results.map(mapRateRow);
  const purchaseOrders = poRows.results.map(mapPoRow);
  const approvals = approvalRows.results.map(mapApprovalRow);

  return {
    translators,
    rates,
    purchaseOrders,
    approvals,
    metrics: {
      translatorCount: translators.length,
      languagePairCount: new Set(rates.map((item) => item.languagePair)).size,
      pendingAmounts: summarizePendingAmounts(purchaseOrders),
      pendingApprovalCount: approvals.filter((item) => item.status === "pending").length,
    },
  };
}

export function summarizePendingAmounts(
  purchaseOrders: PurchaseOrder[],
): Array<{ currency: string; amountCents: number }> {
  const totals = new Map<string, number>();
  for (const item of purchaseOrders) {
    if (item.status === "paid") continue;
    totals.set(item.currency, (totals.get(item.currency) ?? 0) + item.amountCents);
  }
  return [...totals.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currency, amountCents]) => ({ currency, amountCents }));
}

function mutationError(error: unknown): unknown {
  if (error instanceof DomainError) return error;
  const message = error instanceof Error ? error.message : "";
  if (/UNIQUE constraint failed/i.test(message)) {
    return new ConflictError("记录与现有数据冲突");
  }
  if (/FOREIGN KEY constraint failed/i.test(message)) {
    return new ValidationError("关联的译员不存在");
  }
  return error;
}

function changedRows(result: D1ResultLike): number {
  const changes = result.meta?.changes;
  return Number.isSafeInteger(changes) ? Number(changes) : 0;
}

export async function createTranslator(
  db: D1DatabaseLike,
  translator: Translator,
): Promise<void> {
  try {
    await db
      .prepare("INSERT INTO translators (id, name, email, native_language, status, onboarded_at) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(
        translator.id,
        translator.name,
        translator.email,
        translator.nativeLanguage,
        translator.status,
        translator.onboardedAt,
      )
      .run();
  } catch (error) {
    throw mutationError(error);
  }
}

export async function updateTranslator(
  db: D1DatabaseLike,
  translator: Translator,
): Promise<void> {
  try {
    const result = await db
      .prepare("UPDATE translators SET name = ?, email = ?, native_language = ?, status = ?, onboarded_at = ? WHERE id = ?")
      .bind(
        translator.name,
        translator.email,
        translator.nativeLanguage,
        translator.status,
        translator.onboardedAt,
        translator.id,
      )
      .run();
    if (changedRows(result) !== 1) throw new NotFoundError("未找到译员");
  } catch (error) {
    throw mutationError(error);
  }
}

export async function upsertRate(db: D1DatabaseLike, rate: Rate): Promise<void> {
  try {
    await db
      .prepare("INSERT INTO rates (id, translator_id, language_pair, rate_micros, currency, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(translator_id, language_pair) DO UPDATE SET rate_micros = excluded.rate_micros, currency = excluded.currency, updated_at = excluded.updated_at")
      .bind(
        rate.id,
        rate.translatorId,
        rate.languagePair,
        rate.rateMicros,
        rate.currency,
        rate.updatedAt,
      )
      .run();
  } catch (error) {
    throw mutationError(error);
  }
}

export async function createPurchaseOrder(
  db: D1DatabaseLike,
  po: PurchaseOrder,
): Promise<void> {
  try {
    await db
      .prepare("INSERT INTO purchase_orders (id, po_number, translator_id, month, language_pair, word_count, unit_rate_micros, amount_cents, currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
      .bind(
        po.id,
        po.poNumber,
        po.translatorId,
        po.month,
        po.languagePair,
        po.wordCount,
        po.unitRateMicros,
        po.amountCents,
        po.currency,
        po.status,
        po.createdAt,
      )
      .run();
  } catch (error) {
    throw mutationError(error);
  }
}

export async function updatePoStatus(
  db: D1DatabaseLike,
  id: string,
  status: PoStatus,
): Promise<void> {
  const result = await db
    .prepare("UPDATE purchase_orders SET status = ? WHERE id = ?")
    .bind(status, id)
    .run();
  if (changedRows(result) !== 1) throw new NotFoundError("未找到 PO");
}

export async function createApproval(
  db: D1DatabaseLike,
  approval: Approval,
): Promise<void> {
  await db
    .prepare("INSERT INTO approvals (id, kind, payload_json, submitted_by, status, reviewer, note, created_at, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .bind(
      approval.id,
      approval.kind,
      JSON.stringify(approval.payload),
      approval.submittedBy,
      approval.status,
      approval.reviewer,
      approval.note,
      approval.createdAt,
      approval.reviewedAt,
    )
    .run();
}

export async function reviewApproval(
  db: D1DatabaseLike,
  id: string,
  status: Exclude<ApprovalStatus, "pending">,
  reviewer: string,
  note: string,
): Promise<void> {
  const row = await db
    .prepare("SELECT * FROM approvals WHERE id = ?")
    .bind(id)
    .first<Record<string, unknown>>();
  if (!row) throw new NotFoundError("未找到审核项");

  const approval = mapApprovalRow(row);
  if (approval.status !== "pending") throw new ConflictError("该审核项已处理");

  let payload: RateProposal | PoProposal | null = null;
  if (status === "approved") {
    try {
      payload = validateApprovalPayload(approval.kind, approval.payload);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "内容无效";
      throw new UnprocessableEntityError(`审核提案无法处理：${detail}`);
    }
  }

  const now = new Date().toISOString();
  const reviewToken = crypto.randomUUID();
  const claimStatement = db
    .prepare("UPDATE approvals SET review_token = ? WHERE id = ? AND status = 'pending' AND review_token IS NULL")
    .bind(reviewToken, id);
  const finalizeStatement = db
    .prepare("UPDATE approvals SET status = ?, reviewer = ?, note = ?, reviewed_at = ? WHERE id = ? AND status = 'pending' AND review_token = ?")
    .bind(status, reviewer, note, now, id, reviewToken);

  const statements: D1StatementLike[] = [claimStatement];

  if (status === "approved" && approval.kind === "rate") {
    const ratePayload = payload as RateProposal;
    const rateStatement = db
      .prepare("INSERT INTO rates (id, translator_id, language_pair, rate_micros, currency, updated_at) SELECT ?, ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM approvals WHERE id = ? AND status = 'pending' AND review_token = ?) ON CONFLICT(translator_id, language_pair) DO UPDATE SET rate_micros = excluded.rate_micros, currency = excluded.currency, updated_at = excluded.updated_at")
      .bind(
        `rate-${crypto.randomUUID()}`,
        ratePayload.translatorId,
        ratePayload.languagePair,
        ratePayload.rateMicros,
        ratePayload.currency,
        now,
        id,
        reviewToken,
      );
    statements.push(rateStatement);
  }

  if (status === "approved" && approval.kind === "po") {
    const poPayload = payload as PoProposal;
    const poStatement = db
      .prepare("INSERT INTO purchase_orders (id, po_number, translator_id, month, language_pair, word_count, unit_rate_micros, amount_cents, currency, status, created_at) SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM approvals WHERE id = ? AND status = 'pending' AND review_token = ?)")
      .bind(
        `po-${crypto.randomUUID()}`,
        poPayload.poNumber,
        poPayload.translatorId,
        poPayload.month,
        poPayload.languagePair,
        poPayload.wordCount,
        poPayload.unitRateMicros,
        calculateAmountCents(poPayload.wordCount, poPayload.unitRateMicros),
        poPayload.currency,
        poPayload.status,
        now,
        id,
        reviewToken,
      );
    statements.push(poStatement);
  }

  statements.push(finalizeStatement);
  let results: D1ResultLike[];
  try {
    results = await db.batch(statements);
  } catch (error) {
    throw mutationError(error);
  }
  if (changedRows(results[0] ?? {}) !== 1) {
    throw new ConflictError("该审核项已被其他请求处理");
  }
}
