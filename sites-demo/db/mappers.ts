import type {
  Approval,
  ApprovalKind,
  ApprovalStatus,
  PoStatus,
  PurchaseOrder,
  Rate,
  Translator,
  TranslatorStatus,
} from "../lib/types";

type D1Row = Record<string, unknown>;

export function mapTranslatorRow(row: D1Row): Translator {
  return {
    id: String(row.id),
    name: String(row.name),
    email: String(row.email),
    nativeLanguage: String(row.native_language),
    status: String(row.status) as TranslatorStatus,
    onboardedAt: String(row.onboarded_at),
  };
}

export function mapRateRow(row: D1Row): Rate {
  return {
    id: String(row.id),
    translatorId: String(row.translator_id),
    languagePair: String(row.language_pair),
    rateMicros: Number(row.rate_micros),
    currency: String(row.currency),
    updatedAt: String(row.updated_at),
  };
}

export function mapPoRow(row: D1Row): PurchaseOrder {
  return {
    id: String(row.id),
    poNumber: String(row.po_number),
    translatorId: String(row.translator_id),
    month: String(row.month),
    languagePair: String(row.language_pair),
    wordCount: Number(row.word_count),
    unitRateMicros: Number(row.unit_rate_micros),
    amountCents: Number(row.amount_cents),
    currency: String(row.currency),
    status: String(row.status) as PoStatus,
    createdAt: String(row.created_at),
  };
}

export function mapApprovalRow(row: D1Row): Approval {
  return {
    id: String(row.id),
    kind: String(row.kind) as ApprovalKind,
    payload: JSON.parse(String(row.payload_json)) as Approval["payload"],
    submittedBy: String(row.submitted_by),
    status: String(row.status) as ApprovalStatus,
    reviewer: row.reviewer === null ? null : String(row.reviewer),
    note: row.note === null ? null : String(row.note),
    createdAt: String(row.created_at),
    reviewedAt: row.reviewed_at === null ? null : String(row.reviewed_at),
  };
}
