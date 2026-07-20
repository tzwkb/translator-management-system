import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

async function migratedDatabase(): Promise<DatabaseSync> {
  const names = (await readdir(new URL("../drizzle/", import.meta.url)))
    .filter((name) => name.endsWith(".sql"));
  assert.equal(names.length, 1);
  const migration = await readFile(new URL(`../drizzle/${names[0]}`, import.meta.url), "utf8");
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON");
  for (const statement of migration.split("--> statement-breakpoint")) {
    if (statement.trim()) db.exec(statement);
  }
  return db;
}

test("migration enforces business enum and numeric constraints", async () => {
  const db = await migratedDatabase();
  assert.throws(
    () => db.exec("INSERT INTO translators (id, name, email, native_language, status, onboarded_at) VALUES ('tr-1', 'Demo', 'demo@example.test', 'English', 'archived', '2026-07-20')"),
    /CHECK constraint failed/,
  );
  db.exec("INSERT INTO translators (id, name, email, native_language, status, onboarded_at) VALUES ('tr-1', 'Demo', 'demo@example.test', 'English', 'active', '2026-07-20')");
  assert.throws(
    () => db.exec("INSERT INTO purchase_orders (id, po_number, translator_id, month, language_pair, word_count, unit_rate_micros, amount_cents, currency, status, created_at) VALUES ('po-1', 'PO-1', 'tr-1', '2026-07', 'en → zh', -1, 100000, -10, 'CNY', 'void', '2026-07-20')"),
    /CHECK constraint failed/,
  );
  db.close();
});

test("migration creates status indexes and unique approval review tokens", async () => {
  const db = await migratedDatabase();
  const poIndexes = db.prepare("PRAGMA index_list('purchase_orders')").all() as Array<{ name: string }>;
  const approvalIndexes = db.prepare("PRAGMA index_list('approvals')").all() as Array<{ name: string; unique: number }>;
  assert.ok(poIndexes.some((item) => item.name === "purchase_orders_status_idx"));
  assert.ok(approvalIndexes.some((item) => item.name === "approvals_status_idx"));
  assert.ok(approvalIndexes.some((item) => item.name === "approvals_review_token_unique" && item.unique === 1));
  db.close();
});
