import assert from "node:assert/strict";
import test from "node:test";
import { errorResponse } from "../lib/api";
import {
  ConflictError,
  NotFoundError,
  UnprocessableEntityError,
  ValidationError,
} from "../lib/errors";
import {
  MAX_RATE_MICROS,
  MAX_WORD_COUNT,
  normalizePoInput,
  normalizeRateInput,
  normalizeTranslatorInput,
} from "../lib/validation";
import { validateApprovalPayload } from "../lib/approvals";

const validPo = {
  poNumber: " PO-DEMO-1 ",
  translatorId: " tr-1 ",
  month: "2026-07",
  languagePair: " en-US → zh-CN ",
  wordCount: 12_345,
  unitRateMicros: 128_500,
  currency: "cny",
  status: "draft",
};

test("normalizes direct rate and PO inputs with explicit bounds", () => {
  assert.deepEqual(
    normalizeRateInput({
      translatorId: " tr-1 ",
      languagePair: " en-US → zh-CN ",
      rateMicros: 128_500,
      currency: "cny",
    }),
    {
      translatorId: "tr-1",
      languagePair: "en-US → zh-CN",
      rateMicros: 128_500,
      currency: "CNY",
    },
  );
  assert.equal(normalizePoInput(validPo).status, "draft");
  assert.throws(
    () => normalizePoInput({ ...validPo, wordCount: MAX_WORD_COUNT + 1 }),
    /字数.*上限/,
  );
  assert.throws(
    () => normalizeRateInput({ ...validPo, rateMicros: MAX_RATE_MICROS + 1 }),
    /费率.*上限/,
  );
});

test("rejects invalid translator and new PO statuses instead of coercing them", () => {
  assert.throws(
    () => normalizeTranslatorInput({
      name: "林夏",
      email: "linxia@example.test",
      nativeLanguage: "简体中文",
      status: "archived",
      onboardedAt: "2026-07-20",
    }),
    /译员状态无效/,
  );
  assert.throws(() => normalizePoInput({ ...validPo, status: "paid" }), /PO 状态无效/);
});

test("validates onboarding dates by UTC calendar round-trip", () => {
  const translator = {
    name: "林夏",
    email: "linxia@example.test",
    nativeLanguage: "简体中文",
    status: "active",
  };
  assert.equal(
    normalizeTranslatorInput({ ...translator, onboardedAt: "2024-02-29" }).onboardedAt,
    "2024-02-29",
  );
  assert.throws(
    () => normalizeTranslatorInput({ ...translator, onboardedAt: "2026-99-99" }),
    /入库日期.*无效/,
  );
  assert.throws(
    () => normalizeTranslatorInput({ ...translator, onboardedAt: "2025-02-29" }),
    /入库日期.*无效/,
  );
});

test("uses the same normalized schema for proposals and rejects paid PO proposals", () => {
  const direct = normalizeRateInput({
    translatorId: " tr-1 ",
    languagePair: " en-US → zh-CN ",
    rateMicros: 128_500,
    currency: "cny",
  });
  assert.deepEqual(validateApprovalPayload("rate", {
    translatorId: " tr-1 ",
    languagePair: " en-US → zh-CN ",
    rateMicros: 128_500,
    currency: "cny",
  }), direct);
  assert.throws(
    () => validateApprovalPayload("po", { ...validPo, status: "paid" }),
    /PO 状态无效/,
  );
});

test("maps expected domain errors and sanitizes unknown failures", async () => {
  const cases = [
    [new ValidationError("输入错误"), 400, "输入错误"],
    [new NotFoundError("未找到译员"), 404, "未找到译员"],
    [new ConflictError("审核已处理"), 409, "审核已处理"],
    [new UnprocessableEntityError("提案无法解析"), 422, "提案无法解析"],
  ] as const;
  for (const [error, status, message] of cases) {
    const response = errorResponse(error);
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), { error: message });
  }

  const originalError = console.error;
  console.error = () => undefined;
  try {
    const response = errorResponse(new Error("secret sqlite detail"));
    assert.equal(response.status, 500);
    assert.deepEqual(await response.json(), { error: "服务器内部错误" });
  } finally {
    console.error = originalError;
  }
});
