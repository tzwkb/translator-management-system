import { ValidationError } from "./errors";
import type {
  PoProposal,
  PoStatus,
  RateProposal,
  Translator,
  TranslatorStatus,
} from "./types";

export const MAX_WORD_COUNT = 100_000_000;
export const MAX_RATE_MICROS = 100_000_000;
const XML_10_FORBIDDEN_CHARACTER = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/u;
const XML_10_FORBIDDEN_CHARACTERS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/gu;

export function sanitizeXml10Text(value: string): string {
  return value.replace(XML_10_FORBIDDEN_CHARACTERS, "\uFFFD");
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    throw new ValidationError("请求内容无效");
  }
  return value as Record<string, unknown>;
}

export function normalizedText(
  value: unknown,
  label: string,
  maxLength = 160,
): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new ValidationError(`${label}不能为空`);
  }
  const result = value.trim();
  if (result.length > maxLength) {
    throw new ValidationError(`${label}过长`);
  }
  if (XML_10_FORBIDDEN_CHARACTER.test(result)) {
    throw new ValidationError(`${label}包含不支持的控制字符`);
  }
  return result;
}

export function normalizedSafeInteger(
  value: unknown,
  label: string,
  maximum: number,
): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new ValidationError(`${label}必须是非负安全整数`);
  }
  if (Number(value) > maximum) {
    throw new ValidationError(`${label}超过业务上限 ${maximum.toLocaleString("zh-CN")}`);
  }
  return Number(value);
}

export function normalizeTranslatorStatus(value: unknown): TranslatorStatus {
  if (value !== "active" && value !== "inactive") {
    throw new ValidationError("译员状态无效");
  }
  return value;
}

export function normalizePoStatus(
  value: unknown,
  allowPaid: boolean,
): PoStatus {
  const allowed: PoStatus[] = allowPaid
    ? ["draft", "confirmed", "paid"]
    : ["draft", "confirmed"];
  if (!allowed.includes(value as PoStatus)) {
    throw new ValidationError("PO 状态无效");
  }
  return value as PoStatus;
}

function normalizeCurrency(value: unknown): string {
  const currency = normalizedText(value, "币种", 3).toUpperCase();
  if (!/^[A-Z]{3}$/.test(currency)) {
    throw new ValidationError("币种必须是三位字母代码");
  }
  return currency;
}

export function normalizeTranslatorInput(
  value: unknown,
): Omit<Translator, "id"> {
  const input = record(value);
  const email = normalizedText(input.email, "邮箱", 160).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new ValidationError("邮箱格式无效");
  }
  const onboardedAt = normalizedText(input.onboardedAt, "入库日期", 10);
  const parsedOnboardedAt = new Date(`${onboardedAt}T00:00:00.000Z`);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(onboardedAt) ||
    Number.isNaN(parsedOnboardedAt.getTime()) ||
    parsedOnboardedAt.toISOString().slice(0, 10) !== onboardedAt
  ) {
    throw new ValidationError("入库日期格式无效");
  }
  return {
    name: normalizedText(input.name, "姓名", 80),
    email,
    nativeLanguage: normalizedText(input.nativeLanguage, "母语", 80),
    status: normalizeTranslatorStatus(input.status),
    onboardedAt,
  };
}

export function normalizeRateInput(value: unknown): RateProposal {
  const input = record(value);
  return {
    translatorId: normalizedText(input.translatorId, "译员"),
    languagePair: normalizedText(input.languagePair, "语言对", 80),
    rateMicros: normalizedSafeInteger(input.rateMicros, "费率", MAX_RATE_MICROS),
    currency: normalizeCurrency(input.currency),
  };
}

export function normalizePoInput(value: unknown): PoProposal {
  const input = record(value);
  const month = normalizedText(input.month, "月份", 7);
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) {
    throw new ValidationError("月份格式无效");
  }
  return {
    poNumber: normalizedText(input.poNumber, "PO 号", 80),
    translatorId: normalizedText(input.translatorId, "译员"),
    month,
    languagePair: normalizedText(input.languagePair, "语言对", 80),
    wordCount: normalizedSafeInteger(input.wordCount, "字数", MAX_WORD_COUNT),
    unitRateMicros: normalizedSafeInteger(input.unitRateMicros, "费率", MAX_RATE_MICROS),
    currency: normalizeCurrency(input.currency),
    status: normalizePoStatus(input.status, false),
  };
}
