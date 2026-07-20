import assert from "node:assert/strict";
import test from "node:test";
import { mapPoRow, mapRateRow, mapTranslatorRow } from "../db/mappers";

test("maps D1 translator rows to the API model", () => {
  assert.deepEqual(
    mapTranslatorRow({
      id: "tr-demo-1",
      name: "林夏",
      email: "linxia@example.test",
      native_language: "简体中文",
      status: "active",
      onboarded_at: "2026-01-08",
    }),
    {
      id: "tr-demo-1",
      name: "林夏",
      email: "linxia@example.test",
      nativeLanguage: "简体中文",
      status: "active",
      onboardedAt: "2026-01-08",
    },
  );
});

test("maps integer rate and PO values without losing precision", () => {
  assert.equal(
    mapRateRow({
      id: "rate-1",
      translator_id: "tr-demo-1",
      language_pair: "en-US → zh-CN",
      rate_micros: 128_500,
      currency: "CNY",
      updated_at: "2026-07-20T00:00:00.000Z",
    }).rateMicros,
    128_500,
  );
  assert.equal(
    mapPoRow({
      id: "po-1",
      po_number: "PO-DEMO-001",
      translator_id: "tr-demo-1",
      month: "2026-07",
      language_pair: "en-US → zh-CN",
      word_count: 12_345,
      unit_rate_micros: 128_500,
      amount_cents: 158_633,
      currency: "CNY",
      status: "draft",
      created_at: "2026-07-20T00:00:00.000Z",
    }).amountCents,
    158_633,
  );
});
