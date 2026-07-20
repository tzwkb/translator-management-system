import { sql } from "drizzle-orm";
import { check, index, integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const translators = sqliteTable(
  "translators",
  {
    id: text("id").primaryKey(),
    name: text("name").notNull(),
    email: text("email").notNull().unique(),
    nativeLanguage: text("native_language").notNull(),
    status: text("status", { enum: ["active", "inactive"] }).notNull(),
    onboardedAt: text("onboarded_at").notNull(),
  },
  (table) => [
    check("translators_status_check", sql`${table.status} IN ('active', 'inactive')`),
  ],
);

export const rates = sqliteTable(
  "rates",
  {
    id: text("id").primaryKey(),
    translatorId: text("translator_id")
      .notNull()
      .references(() => translators.id),
    languagePair: text("language_pair").notNull(),
    rateMicros: integer("rate_micros").notNull(),
    currency: text("currency").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    uniqueIndex("rates_translator_pair_idx").on(
      table.translatorId,
      table.languagePair,
    ),
    check("rates_rate_micros_check", sql`${table.rateMicros} BETWEEN 0 AND 100000000`),
  ],
);

export const purchaseOrders = sqliteTable(
  "purchase_orders",
  {
    id: text("id").primaryKey(),
    poNumber: text("po_number").notNull().unique(),
    translatorId: text("translator_id")
      .notNull()
      .references(() => translators.id),
    month: text("month").notNull(),
    languagePair: text("language_pair").notNull(),
    wordCount: integer("word_count").notNull(),
    unitRateMicros: integer("unit_rate_micros").notNull(),
    amountCents: integer("amount_cents").notNull(),
    currency: text("currency").notNull(),
    status: text("status", { enum: ["draft", "confirmed", "paid"] }).notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("purchase_orders_status_idx").on(table.status),
    check("purchase_orders_status_check", sql`${table.status} IN ('draft', 'confirmed', 'paid')`),
    check("purchase_orders_word_count_check", sql`${table.wordCount} BETWEEN 0 AND 100000000`),
    check("purchase_orders_rate_check", sql`${table.unitRateMicros} BETWEEN 0 AND 100000000`),
    check("purchase_orders_amount_check", sql`${table.amountCents} >= 0`),
  ],
);

export const approvals = sqliteTable(
  "approvals",
  {
    id: text("id").primaryKey(),
    kind: text("kind", { enum: ["rate", "po"] }).notNull(),
    payloadJson: text("payload_json").notNull(),
    submittedBy: text("submitted_by").notNull(),
    status: text("status", {
      enum: ["pending", "approved", "rejected"],
    }).notNull(),
    reviewer: text("reviewer"),
    note: text("note"),
    createdAt: text("created_at").notNull(),
    reviewedAt: text("reviewed_at"),
    reviewToken: text("review_token").unique(),
  },
  (table) => [
    index("approvals_status_idx").on(table.status),
    check("approvals_kind_check", sql`${table.kind} IN ('rate', 'po')`),
    check("approvals_status_check", sql`${table.status} IN ('pending', 'approved', 'rejected')`),
  ],
);
