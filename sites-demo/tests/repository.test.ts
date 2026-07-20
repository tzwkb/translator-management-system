import assert from "node:assert/strict";
import test from "node:test";
import {
  createTranslator,
  ensureDatabase,
  reviewApproval,
  updateTranslator,
  type D1DatabaseLike,
  type D1ResultLike,
  type D1StatementLike,
} from "../db/repository";
import { ConflictError, NotFoundError, UnprocessableEntityError } from "../lib/errors";

class FakeStatement implements D1StatementLike {
  bindings: unknown[] = [];

  constructor(
    readonly sql: string,
    private readonly firstResult: Record<string, unknown> | null = null,
    private readonly runChanges = 1,
    private readonly runError: Error | null = null,
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

  async run(): Promise<D1ResultLike> {
    if (this.runError) throw this.runError;
    return { meta: { changes: this.runChanges } };
  }
}

class FakeDb implements D1DatabaseLike {
  readonly prepared: FakeStatement[] = [];
  readonly batches: D1StatementLike[][] = [];

  constructor(
    private readonly approval: Record<string, unknown> | null = null,
    private readonly runChanges = 1,
    private readonly runError: Error | null = null,
  ) {}

  prepare(sql: string): FakeStatement {
    const statement = new FakeStatement(
      sql,
      sql.startsWith("SELECT") ? this.approval : null,
      this.runChanges,
      this.runError,
    );
    this.prepared.push(statement);
    return statement;
  }

  async batch(statements: D1StatementLike[]): Promise<D1ResultLike[]> {
    this.batches.push(statements);
    return statements.map(() => ({ meta: { changes: 1 } }));
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
  assert.equal(db.batches[0].length, 3);
  assert.match((db.batches[0][0] as FakeStatement).sql, /review_token.*status = 'pending'/);
  assert.match((db.batches[0][1] as FakeStatement).sql, /INSERT INTO rates[\s\S]*WHERE EXISTS[\s\S]*review_token/);
  assert.match((db.batches[0][2] as FakeStatement).sql, /UPDATE approvals/);
  const reviewToken = (db.batches[0][0] as FakeStatement).bindings[0];
  assert.equal((db.batches[0][1] as FakeStatement).bindings.at(-1), reviewToken);
  assert.equal((db.batches[0][2] as FakeStatement).bindings.at(-1), reviewToken);
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
  assert.equal(db.batches[0].length, 2);
  assert.match((db.batches[0][0] as FakeStatement).sql, /review_token/);
  assert.match((db.batches[0][1] as FakeStatement).sql, /UPDATE approvals/);
});

class RacingDb implements D1DatabaseLike {
  readonly batches: D1StatementLike[][] = [];
  businessWrites = 0;
  private claimed = false;

  constructor(private readonly approval: Record<string, unknown>) {}

  prepare(sql: string): FakeStatement {
    return new FakeStatement(sql, sql.startsWith("SELECT") ? { ...this.approval } : null);
  }

  async batch(statements: D1StatementLike[]): Promise<D1ResultLike[]> {
    this.batches.push(statements);
    const wonClaim = !this.claimed;
    if (wonClaim) this.claimed = true;
    if (wonClaim && statements.some((item) => (item as FakeStatement).sql.startsWith("INSERT INTO rates"))) {
      this.businessWrites += 1;
    }
    return statements.map((_, index) => ({
      meta: { changes: index === 0 ? (wonClaim ? 1 : 0) : (wonClaim ? 1 : 0) },
    }));
  }
}

test("concurrent approve and reject allow one CAS winner and at most one business write", async () => {
  const db = new RacingDb({
    id: "approval-race",
    kind: "rate",
    payload_json: JSON.stringify({
      translatorId: "tr-demo-1",
      languagePair: "fr-FR → zh-CN",
      rateMicros: 139_000,
      currency: "CNY",
    }),
    submitted_by: "Demo Agent",
    status: "pending",
    reviewer: null,
    note: null,
    created_at: "2026-07-20T00:00:00.000Z",
    reviewed_at: null,
    review_token: null,
  });

  const results = await Promise.allSettled([
    reviewApproval(db, "approval-race", "approved", "Boss A", "批准"),
    reviewApproval(db, "approval-race", "rejected", "Boss B", "驳回"),
  ]);

  assert.equal(results.filter((item) => item.status === "fulfilled").length, 1);
  const rejected = results.find((item) => item.status === "rejected");
  assert.ok(rejected && rejected.status === "rejected" && rejected.reason instanceof ConflictError);
  assert.ok(db.businessWrites <= 1);
  assert.equal(db.batches.length, 2);
});

test("maps missing, stale, malformed, and unique-conflict mutations to domain errors", async () => {
  await assert.rejects(
    reviewApproval(new FakeDb(), "missing", "approved", "Boss", "批准"),
    NotFoundError,
  );
  await assert.rejects(
    reviewApproval(new FakeDb({
      id: "approval-bad",
      kind: "rate",
      payload_json: "{",
      submitted_by: "Agent",
      status: "pending",
      reviewer: null,
      note: null,
      created_at: "2026-07-20T00:00:00.000Z",
      reviewed_at: null,
      review_token: null,
    }), "approval-bad", "approved", "Boss", "批准"),
    UnprocessableEntityError,
  );
  await assert.rejects(
    updateTranslator(new FakeDb(null, 0), {
      id: "missing",
      name: "Demo",
      email: "demo@example.test",
      nativeLanguage: "English",
      status: "active",
      onboardedAt: "2026-07-20",
    }),
    NotFoundError,
  );
  await assert.rejects(
    createTranslator(new FakeDb(null, 1, new Error("UNIQUE constraint failed: translators.email")), {
      id: "tr-2",
      name: "Demo",
      email: "demo@example.test",
      nativeLanguage: "English",
      status: "active",
      onboardedAt: "2026-07-20",
    }),
    ConflictError,
  );
});
