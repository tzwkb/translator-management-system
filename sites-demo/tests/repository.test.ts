import assert from "node:assert/strict";
import test from "node:test";
import {
  ensureDatabase,
  reviewApproval,
  type D1DatabaseLike,
  type D1StatementLike,
} from "../db/repository";

class FakeStatement implements D1StatementLike {
  bindings: unknown[] = [];

  constructor(
    readonly sql: string,
    private readonly firstResult: Record<string, unknown> | null = null,
  ) {}

  bind(...values: unknown[]): D1StatementLike {
    this.bindings = values;
    return this;
  }

  async first<T>(): Promise<T | null> {
    return this.firstResult as T | null;
  }

  async all<T>(): Promise<{ results: T[] }> {
    return { results: [] };
  }

  async run(): Promise<unknown> {
    return {};
  }
}

class FakeDb implements D1DatabaseLike {
  readonly prepared: FakeStatement[] = [];
  readonly batches: D1StatementLike[][] = [];

  constructor(private readonly approval: Record<string, unknown> | null = null) {}

  prepare(sql: string): FakeStatement {
    const statement = new FakeStatement(
      sql,
      sql.startsWith("SELECT") ? this.approval : null,
    );
    this.prepared.push(statement);
    return statement;
  }

  async batch(statements: D1StatementLike[]): Promise<unknown[]> {
    this.batches.push(statements);
    return statements.map(() => ({}));
  }
}

test("initializes schema and example seeds with idempotent single statements", async () => {
  const db = new FakeDb();
  await ensureDatabase(db);

  assert.equal(db.batches.length, 2);
  assert.ok(db.prepared.some((item) => /CREATE TABLE IF NOT EXISTS translators/.test(item.sql)));
  assert.ok(db.prepared.some((item) => /INSERT OR IGNORE INTO translators/.test(item.sql)));
  assert.ok(
    db.prepared.every(
      (item) => item.sql.split(";").filter((part) => part.trim()).length <= 1,
    ),
  );
});

test("approving a rate proposal atomically writes the rate and review status", async () => {
  const db = new FakeDb({
    id: "approval-1",
    kind: "rate",
    payload_json: JSON.stringify({
      translatorId: "tr-demo-1",
      languagePair: "en-US → zh-CN",
      rateMicros: 135_000,
      currency: "CNY",
    }),
    submitted_by: "Demo Agent",
    status: "pending",
    reviewer: null,
    note: null,
    created_at: "2026-07-20T00:00:00.000Z",
    reviewed_at: null,
  });

  await reviewApproval(db, "approval-1", "approved", "Demo Boss", "核价通过");

  assert.equal(db.batches.length, 1);
  assert.equal(db.batches[0].length, 2);
  assert.match((db.batches[0][0] as FakeStatement).sql, /INSERT INTO rates/);
  assert.match((db.batches[0][1] as FakeStatement).sql, /UPDATE approvals/);
});

test("rejecting a proposal updates only the approval record", async () => {
  const db = new FakeDb({
    id: "approval-2",
    kind: "po",
    payload_json: "{}",
    submitted_by: "Demo Agent",
    status: "pending",
    reviewer: null,
    note: null,
    created_at: "2026-07-20T00:00:00.000Z",
    reviewed_at: null,
  });

  await reviewApproval(db, "approval-2", "rejected", "Demo Boss", "信息不完整");

  assert.equal(db.batches.length, 1);
  assert.equal(db.batches[0].length, 1);
  assert.match((db.batches[0][0] as FakeStatement).sql, /UPDATE approvals/);
});
