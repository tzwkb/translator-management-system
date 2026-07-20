import assert from "node:assert/strict";
import test from "node:test";
import {
  MAX_RATE_PER_WORD,
  preparePoSubmission,
  prepareRateSubmission,
  safePoEstimate,
} from "../lib/form-safety";
import { MAX_RATE_MICROS, MAX_WORD_COUNT } from "../lib/validation";

const rateForm = {
  translatorId: "tr-1",
  languagePair: "en-US → zh-CN",
  rate: "0.12",
  currency: "CNY",
};

const poForm = {
  poNumber: "PO-1",
  translatorId: "tr-1",
  month: "2026-07",
  languagePair: "en-US → zh-CN",
  wordCount: "1000",
  unitRate: "0.12",
  currency: "CNY",
  status: "draft" as const,
};

test("over-limit PO values render a safe estimate instead of throwing", () => {
  assert.doesNotThrow(() => safePoEstimate("100000001", "0.12", "CNY"));
  assert.equal(safePoEstimate("100000001", "0.12", "CNY"), "超出范围");
  assert.doesNotThrow(() => safePoEstimate("1000", "101", "CNY"));
  assert.equal(safePoEstimate("1000", "101", "CNY"), "超出范围");
});

test("over-limit submissions return Chinese feedback without throwing", () => {
  const rateResult = prepareRateSubmission({ ...rateForm, rate: "101" });
  assert.equal(rateResult.ok, false);
  if (!rateResult.ok) assert.match(rateResult.error, /费率.*超出范围/);

  const poResult = preparePoSubmission({ ...poForm, wordCount: "100000001" });
  assert.equal(poResult.ok, false);
  if (!poResult.ok) assert.match(poResult.error, /PO.*超出范围/);
});

test("client numeric maxima exactly match the server limits", () => {
  assert.equal(MAX_RATE_PER_WORD * 1_000_000, MAX_RATE_MICROS);
  assert.equal(MAX_WORD_COUNT, 100_000_000);
});
