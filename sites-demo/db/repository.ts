import { calculateAmountCents } from "../lib/money";
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
  run(): Promise<unknown>;
}

export interface D1DatabaseLike {
  prepare(sql: string): D1StatementLike;
  batch(statements: D1StatementLike[]): Promise<unknown[]>;
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
    rate_micros INTEGER NOT NULL,
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
    word_count INTEGER NOT NULL,
    unit_rate_micros INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
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
    reviewed_at TEXT
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
      pendingAmountCents: purchaseOrders
        .filter((item) => item.status !== "paid")
        .reduce((total, item) => total + item.amountCents, 0),
      pendingApprovalCount: approvals.filter((item) => item.status === "pending").length,
    },
  };
}

export async function createTranslator(
  db: D1DatabaseLike,
  translator: Translator,
): Promise<void> {
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
}

export async function updateTranslator(
  db: D1DatabaseLike,
  translator: Translator,
): Promise<void> {
  await db
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
}

export async function upsertRate(db: D1DatabaseLike, rate: Rate): Promise<void> {
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
}

export async function createPurchaseOrder(
  db: D1DatabaseLike,
  po: PurchaseOrder,
): Promise<void> {
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
}

export async function updatePoStatus(
  db: D1DatabaseLike,
  id: string,
  status: PoStatus,
): Promise<void> {
  await db
    .prepare("UPDATE purchase_orders SET status = ? WHERE id = ?")
    .bind(status, id)
    .run();
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
  if (!row) throw new Error("未找到审核项");

  const approval = mapApprovalRow(row);
  if (approval.status !== "pending") throw new Error("该审核项已处理");

  const now = new Date().toISOString();
  const reviewStatement = db
    .prepare("UPDATE approvals SET status = ?, reviewer = ?, note = ?, reviewed_at = ? WHERE id = ? AND status = 'pending'")
    .bind(status, reviewer, note, now, id);

  if (status === "rejected") {
    await db.batch([reviewStatement]);
    return;
  }

  if (approval.kind === "rate") {
    const payload = approval.payload as RateProposal;
    const rateStatement = db
      .prepare("INSERT INTO rates (id, translator_id, language_pair, rate_micros, currency, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(translator_id, language_pair) DO UPDATE SET rate_micros = excluded.rate_micros, currency = excluded.currency, updated_at = excluded.updated_at")
      .bind(
        `rate-${crypto.randomUUID()}`,
        payload.translatorId,
        payload.languagePair,
        payload.rateMicros,
        payload.currency,
        now,
      );
    await db.batch([rateStatement, reviewStatement]);
    return;
  }

  const payload = approval.payload as PoProposal;
  const poStatement = db
    .prepare("INSERT INTO purchase_orders (id, po_number, translator_id, month, language_pair, word_count, unit_rate_micros, amount_cents, currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .bind(
      `po-${crypto.randomUUID()}`,
      payload.poNumber,
      payload.translatorId,
      payload.month,
      payload.languagePair,
      payload.wordCount,
      payload.unitRateMicros,
      calculateAmountCents(payload.wordCount, payload.unitRateMicros),
      payload.currency,
      payload.status,
      now,
    );
  await db.batch([poStatement, reviewStatement]);
}
