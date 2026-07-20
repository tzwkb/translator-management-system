import { ValidationError } from "./errors";
import { MAX_RATE_MICROS, MAX_WORD_COUNT } from "./validation";

export function parseRateMicros(value: string | number): number {
  const rate = typeof value === "number" ? value : Number(value);
  const rateMicros = Math.round(rate * 1_000_000);
  if (!Number.isFinite(rate) || rate < 0 || !Number.isSafeInteger(rateMicros)) {
    throw new ValidationError("Rate must be a non-negative safe number");
  }
  if (rateMicros > MAX_RATE_MICROS) {
    throw new ValidationError("Rate exceeds the business maximum");
  }
  return rateMicros;
}

export function calculateAmountCents(
  wordCount: number,
  rateMicros: number,
): number {
  if (!Number.isSafeInteger(wordCount) || wordCount < 0 || wordCount > MAX_WORD_COUNT) {
    throw new ValidationError("Word count must be a non-negative safe integer within the business limit");
  }
  if (!Number.isSafeInteger(rateMicros) || rateMicros < 0 || rateMicros > MAX_RATE_MICROS) {
    throw new ValidationError("Rate must be a non-negative safe integer in micros within the business limit");
  }
  const amount =
    (BigInt(wordCount) * BigInt(rateMicros) + BigInt(5_000)) / BigInt(10_000);
  if (amount > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new ValidationError("Calculated amount exceeds the safe integer range");
  }
  return Number(amount);
}

export function formatRate(rateMicros: number): string {
  return (rateMicros / 1_000_000).toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

export function formatCurrency(amountCents: number, currency: string): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amountCents / 100);
}
