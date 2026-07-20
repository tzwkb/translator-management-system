export type DemoRole = "boss" | "editor" | "viewer" | "agent";
export type TranslatorStatus = "active" | "inactive";
export type PoStatus = "draft" | "confirmed" | "paid";
export type ApprovalStatus = "pending" | "approved" | "rejected";
export type ApprovalKind = "rate" | "po";

export type Translator = {
  id: string;
  name: string;
  email: string;
  nativeLanguage: string;
  status: TranslatorStatus;
  onboardedAt: string;
};

export type Rate = {
  id: string;
  translatorId: string;
  languagePair: string;
  rateMicros: number;
  currency: string;
  updatedAt: string;
};

export type PurchaseOrder = {
  id: string;
  poNumber: string;
  translatorId: string;
  month: string;
  languagePair: string;
  wordCount: number;
  unitRateMicros: number;
  amountCents: number;
  currency: string;
  status: PoStatus;
  createdAt: string;
};

export type RateProposal = {
  translatorId: string;
  languagePair: string;
  rateMicros: number;
  currency: string;
};

export type PoProposal = {
  poNumber: string;
  translatorId: string;
  month: string;
  languagePair: string;
  wordCount: number;
  unitRateMicros: number;
  currency: string;
  status: PoStatus;
};

export type Approval = {
  id: string;
  kind: ApprovalKind;
  payload: RateProposal | PoProposal;
  submittedBy: string;
  status: ApprovalStatus;
  reviewer: string | null;
  note: string | null;
  createdAt: string;
  reviewedAt: string | null;
};

export type WorkspaceData = {
  translators: Translator[];
  rates: Rate[];
  purchaseOrders: PurchaseOrder[];
  approvals: Approval[];
  metrics: {
    translatorCount: number;
    languagePairCount: number;
    pendingAmounts: Array<{ currency: string; amountCents: number }>;
    pendingApprovalCount: number;
  };
};
