export function parseRateMicros(value: string | number): number {
  const rate = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(rate) || rate < 0) {
    throw new Error("Rate must be a non-negative number");
  }
  return Math.round(rate * 1_000_000);
}

export function calculateAmountCents(
  wordCount: number,
  rateMicros: number,
): number {
  if (!Number.isInteger(wordCount) || wordCount < 0) {
    throw new Error("Word count must be a non-negative integer");
  }
  if (!Number.isInteger(rateMicros) || rateMicros < 0) {
    throw new Error("Rate must be a non-negative integer in micros");
  }
  return Math.round((wordCount * rateMicros) / 10_000);
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
