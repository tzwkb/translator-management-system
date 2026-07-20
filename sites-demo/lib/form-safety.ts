import { calculateAmountCents, formatCurrency, parseRateMicros } from "./money";
import type { PoProposal, RateProposal } from "./types";
import {
  MAX_RATE_MICROS,
  normalizePoInput,
  normalizeRateInput,
} from "./validation";

export const MAX_RATE_PER_WORD = MAX_RATE_MICROS / 1_000_000;

type SubmissionResult<T> =
  | { ok: true; payload: T }
  | { ok: false; error: string };

type RateFormInput = {
  translatorId: string;
  languagePair: string;
  rate: string;
  currency: string;
};

type PoFormInput = {
  poNumber: string;
  translatorId: string;
  month: string;
  languagePair: string;
  wordCount: string;
  unitRate: string;
  currency: string;
  status: string;
};

export function prepareRateSubmission(
  form: RateFormInput,
): SubmissionResult<RateProposal> {
  try {
    return {
      ok: true,
      payload: normalizeRateInput({
        translatorId: form.translatorId,
        languagePair: form.languagePair,
        rateMicros: parseRateMicros(form.rate),
        currency: form.currency,
      }),
    };
  } catch {
    return { ok: false, error: "费率输入无效或超出范围，请检查后重试" };
  }
}

export function preparePoSubmission(
  form: PoFormInput,
): SubmissionResult<PoProposal> {
  try {
    return {
      ok: true,
      payload: normalizePoInput({
        poNumber: form.poNumber,
        translatorId: form.translatorId,
        month: form.month,
        languagePair: form.languagePair,
        wordCount: Number(form.wordCount),
        unitRateMicros: parseRateMicros(form.unitRate),
        currency: form.currency,
        status: form.status,
      }),
    };
  } catch {
    return { ok: false, error: "PO 输入无效或超出范围，请检查后重试" };
  }
}

export function safePoEstimate(
  wordCount: string,
  unitRate: string,
  currency: string,
): string {
  try {
    return formatCurrency(
      calculateAmountCents(
        Number(wordCount || 0),
        parseRateMicros(unitRate || 0),
      ),
      currency,
    );
  } catch {
    return "超出范围";
  }
}
