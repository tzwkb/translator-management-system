import { calculateAmountCents, formatCurrency, formatRate } from "./money";
import type { Approval, Translator } from "./types";

function translatorName(translators: Translator[], id: string): string {
  return translators.find((item) => item.id === id)?.name ?? "未找到译员";
}

export function formatApprovalSummary(
  approval: Approval,
  translators: Translator[],
): string {
  const payload = approval.payload;
  if (approval.kind === "rate" && "rateMicros" in payload) {
    return `${translatorName(translators, payload.translatorId)} · ${payload.languagePair} · ${formatRate(payload.rateMicros)} ${payload.currency}/字`;
  }
  if ("poNumber" in payload) {
    const statusLabel = payload.status === "confirmed" ? "已确认" : "草稿";
    const amountCents = calculateAmountCents(
      payload.wordCount,
      payload.unitRateMicros,
    );
    return [
      payload.poNumber,
      translatorName(translators, payload.translatorId),
      payload.month,
      payload.languagePair,
      `${payload.wordCount.toLocaleString("zh-CN")} 字`,
      `${formatRate(payload.unitRateMicros)} ${payload.currency}/字`,
      formatCurrency(amountCents, payload.currency),
      statusLabel,
    ].join(" · ");
  }
  return "待审内容";
}
