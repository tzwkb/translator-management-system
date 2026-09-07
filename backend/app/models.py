"""SQLAlchemy 数据模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime,
                        ForeignKey, Index, Integer, LargeBinary, Numeric, String,
                        Text, UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .security import dec, mask


def _f(x):
    """nullable Numeric -> float | None"""
    return float(x) if x is not None else None


class Translator(Base):
    __tablename__ = "translators"
    id: Mapped[int] = mapped_column(primary_key=True)
    # 基础信息
    name: Mapped[str] = mapped_column(String(100))
    wechat: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    location: Mapped[Optional[str]] = mapped_column(String(200))
    timezone: Mapped[Optional[str]] = mapped_column(String(50))
    native_language: Mapped[Optional[str]] = mapped_column(String(50))
    onboarding_date: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Active", index=True)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    entity_type: Mapped[Optional[str]] = mapped_column(String(20))
    # 专业能力
    language_pairs: Mapped[Optional[str]] = mapped_column(String(200))
    translation_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    mtpe_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    review_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    lqa_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    rate_confirmed_date: Mapped[Optional[str]] = mapped_column(String(20))
    domains: Mapped[Optional[str]] = mapped_column(Text)
    text_types: Mapped[Optional[str]] = mapped_column(Text)
    cat_tools: Mapped[Optional[str]] = mapped_column(Text)
    internal_rating: Mapped[Optional[str]] = mapped_column(String(20))
    manual_rating: Mapped[Optional[str]] = mapped_column(String(20))
    manual_rating_reason: Mapped[Optional[str]] = mapped_column(Text)
    # 质量数据（由质量联动自动更新）
    trial_result: Mapped[Optional[str]] = mapped_column(String(50))
    recent_qa_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    cumulative_qa_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    low_error_count: Mapped[int] = mapped_column(Integer, default=0)
    low_error_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    # 项目分配
    current_project: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[Optional[str]] = mapped_column(String(50))
    daily_output: Mapped[Optional[int]] = mapped_column(Integer)
    cumulative_word_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # 财务信息
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    settlement_mode: Mapped[str] = mapped_column(
        String(20), default="monthly", server_default=text("'monthly'"),
    )
    invoice_type: Mapped[Optional[str]] = mapped_column(String(50))
    tax_deduction: Mapped[Optional[str]] = mapped_column(String(50))
    cumulative_unpaid: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    contract_status: Mapped[Optional[str]] = mapped_column(String(50))
    contract_expiry: Mapped[Optional[str]] = mapped_column(String(20))
    nda_signed: Mapped[Optional[bool]] = mapped_column(Boolean)
    # 谈判记录（由报价联动自动更新）
    negotiation_status: Mapped[Optional[str]] = mapped_column(String(50))
    last_negotiation_date: Mapped[Optional[str]] = mapped_column(String(20))
    post_negotiation_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    rate_reduction_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    accepted_reduction: Mapped[Optional[bool]] = mapped_column(Boolean)
    negotiation_notes: Mapped[Optional[str]] = mapped_column(Text)
    # 绩效与沟通
    punctuality_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    responsiveness: Mapped[Optional[str]] = mapped_column(String(50))
    complaint_count: Mapped[int] = mapped_column(Integer, default=0)
    deduction_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    cooperation_rating: Mapped[Optional[str]] = mapped_column(String(20))
    last_contact: Mapped[Optional[str]] = mapped_column(String(20))
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 人录入字段（新增/编辑表单可填）
    EDITABLE = ("name", "wechat", "email", "location", "timezone", "native_language",
                "onboarding_date", "status", "source", "gender", "entity_type",
                "translation_rate",
                "mtpe_rate", "review_rate", "lqa_rate", "rate_confirmed_date", "domains",
                "text_types", "cat_tools", "manual_rating", "manual_rating_reason",
                "trial_result", "current_project",
                "role", "daily_output", "currency",
                "payment_method", "settlement_mode", "invoice_type", "tax_deduction", "contract_status",
                "contract_expiry", "nda_signed", "punctuality_rate", "responsiveness",
                "cooperation_rating", "last_contact", "remarks")
    # 系统自动算字段（联动维护，只读）
    DERIVED = ("internal_rating", "recent_qa_score", "cumulative_qa_score", "low_error_count", "low_error_rate",
               "complaint_count", "deduction_total", "negotiation_status", "last_negotiation_date",
               "post_negotiation_rate", "rate_reduction_pct", "accepted_reduction",
               "negotiation_notes", "cumulative_unpaid", "cumulative_word_count", "language_pairs")

    def as_dict(self):
        return {
            "id": self.id, "name": self.name, "wechat": self.wechat, "email": self.email,
            "location": self.location, "timezone": self.timezone,
            "native_language": self.native_language, "onboarding_date": self.onboarding_date,
            "status": self.status, "source": self.source,
            "gender": self.gender, "entity_type": self.entity_type,
            "language_pairs": getattr(self, "_cached_lp", None) or self.language_pairs or "", "translation_rate": _f(self.translation_rate),
            "mtpe_rate": _f(self.mtpe_rate), "review_rate": _f(self.review_rate),
            "lqa_rate": _f(self.lqa_rate), "rate_confirmed_date": self.rate_confirmed_date,
            "domains": self.domains, "text_types": self.text_types, "cat_tools": self.cat_tools,
            "internal_rating": self.internal_rating, "manual_rating": self.manual_rating,
            "manual_rating_reason": self.manual_rating_reason,
            "trial_result": self.trial_result,
            "recent_qa_score": _f(self.recent_qa_score),
            "cumulative_qa_score": _f(self.cumulative_qa_score),
            "low_error_count": self.low_error_count, "low_error_rate": _f(self.low_error_rate),
            "current_project": self.current_project, "role": self.role,
            "current_projects": getattr(self, "_cached_current_projects", []),
            "daily_output": self.daily_output,
            "cumulative_word_count": self.cumulative_word_count,
            "currency": self.currency, "payment_method": self.payment_method,
            "settlement_mode": self.settlement_mode,
            "invoice_type": self.invoice_type, "tax_deduction": self.tax_deduction,
            "cumulative_unpaid": _f(self.cumulative_unpaid), "contract_status": self.contract_status,
            "contract_expiry": self.contract_expiry, "nda_signed": self.nda_signed,
            "negotiation_status": self.negotiation_status,
            "last_negotiation_date": self.last_negotiation_date,
            "post_negotiation_rate": _f(self.post_negotiation_rate),
            "rate_reduction_pct": _f(self.rate_reduction_pct),
            "accepted_reduction": self.accepted_reduction, "negotiation_notes": self.negotiation_notes,
            "punctuality_rate": _f(self.punctuality_rate), "responsiveness": self.responsiveness,
            "complaint_count": self.complaint_count, "deduction_total": _f(self.deduction_total),
            "cooperation_rating": self.cooperation_rating, "last_contact": self.last_contact,
            "remarks": self.remarks,
            "computed_availability": getattr(self, "_computed_availability", None),
            "computed_load_pct": getattr(self, "_computed_load_pct", None),
            "capacity_month": getattr(self, "_capacity_month", None),
            "effective_availability": getattr(self, "_effective_availability", None),
            "capacity_override_status": getattr(self, "_capacity_override_status", None),
            "capacity_override_reason": getattr(self, "_capacity_override_reason", None),
            "availability_conflict": getattr(self, "_availability_conflict", False),
            "availability_basis": getattr(self, "_availability_basis", []),
            "capacity_data_complete": getattr(self, "_capacity_data_complete", True),
            "capacity_issues": getattr(self, "_capacity_issues", []),
            "aliases": getattr(self, "_cached_aliases", []),
        }


class TranslatorIntakeInvite(Base):
    __tablename__ = "translator_intake_invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    translator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("translators.id"))
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    revision: Mapped[int] = mapped_column(Integer, default=0)


class TranslatorIntakeSubmission(Base):
    __tablename__ = "translator_intake_submissions"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'needs_info', 'approved', 'rejected')",
                        name="ck_translator_intake_submissions_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    invite_id: Mapped[int] = mapped_column(ForeignKey("translator_intake_invites.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    translator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("translators.id"))


class TranslatorAlias(Base):
    __tablename__ = "translator_aliases"
    __table_args__ = (
        UniqueConstraint(
            "normalized_alias",
            name="uq_translator_aliases_normalized_alias",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(
        ForeignKey("translators.id"),
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(200))
    normalized_alias: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def as_dict(self):
        return {
            "id": self.id,
            "translator_id": self.translator_id,
            "alias": self.alias,
            "normalized_alias": self.normalized_alias,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if self.created_at else None,
        }


class TranslatorProjectExperience(Base):
    __tablename__ = "translator_project_experiences"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    cooperation_source: Mapped[str] = mapped_column(String(20), index=True)
    project_status: Mapped[str] = mapped_column(String(20), index=True)
    project_name: Mapped[str] = mapped_column(String(200))
    external_company: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[Optional[str]] = mapped_column(String(50))
    source_lang: Mapped[Optional[str]] = mapped_column(String(20))
    target_lang: Mapped[Optional[str]] = mapped_column(String(20))
    start_date: Mapped[Optional[str]] = mapped_column(String(20))
    end_date: Mapped[Optional[str]] = mapped_column(String(20))
    remaining_volume: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    deadline: Mapped[Optional[str]] = mapped_column(String(20))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {
            "id": self.id,
            "translator_id": self.translator_id,
            "cooperation_source": self.cooperation_source,
            "project_status": self.project_status,
            "project_name": self.project_name,
            "external_company": self.external_company,
            "role": self.role,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "remaining_volume": _f(self.remaining_volume),
            "deadline": self.deadline,
            "remarks": self.remarks,
        }


class RateChange(Base):
    __tablename__ = "rate_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    change_date: Mapped[str] = mapped_column(String(20))
    source_lang: Mapped[Optional[str]] = mapped_column(String(20))
    target_lang: Mapped[Optional[str]] = mapped_column(String(20))
    task_type: Mapped[Optional[str]] = mapped_column(String(50))
    original_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    new_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    negotiator: Mapped[Optional[str]] = mapped_column(String(100))
    reason: Mapped[Optional[str]] = mapped_column(String(100))
    result: Mapped[Optional[str]] = mapped_column(String(20))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id, "change_date": self.change_date,
                "source_lang": self.source_lang, "target_lang": self.target_lang,
                "task_type": self.task_type,
                "original_rate": _f(self.original_rate),
                "new_rate": _f(self.new_rate),
                "negotiator": self.negotiator, "reason": self.reason, "result": self.result,
                "remarks": self.remarks}


class PO(Base):
    __tablename__ = "po_settlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    settlement_month: Mapped[str] = mapped_column(String(7), index=True)
    project: Mapped[Optional[str]] = mapped_column(String(200))
    source_lang: Mapped[Optional[str]] = mapped_column(String(20))
    target_lang: Mapped[Optional[str]] = mapped_column(String(20))
    role: Mapped[Optional[str]] = mapped_column(String(50))
    word_count: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    status: Mapped[str] = mapped_column(String(20), default="未开票", index=True)
    po_number: Mapped[Optional[str]] = mapped_column(String(50))
    pricing_mode: Mapped[str] = mapped_column(
        String(20), default="per_1000", server_default=text("'per_1000'"),
    )
    source_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255))
    source_row: Mapped[Optional[int]] = mapped_column(Integer)
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id,
                "settlement_month": self.settlement_month, "project": self.project, "role": self.role,
                "source_lang": self.source_lang, "target_lang": self.target_lang,
                "word_count": _f(self.word_count), "rate": _f(self.rate), "amount": _f(self.amount),
                "currency": self.currency, "status": self.status, "po_number": self.po_number,
                "pricing_mode": self.pricing_mode, "source_key": self.source_key,
                "source_name": self.source_name, "source_row": self.source_row,
                "remarks": self.remarks}


class POImportBatch(Base):
    __tablename__ = "po_import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[str] = mapped_column(String(50))
    source_format: Mapped[str] = mapped_column(String(20), index=True)
    parser_version: Mapped[str] = mapped_column(String(30))
    file_name: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    sheet: Mapped[Optional[str]] = mapped_column(String(255))
    header_row: Mapped[Optional[int]] = mapped_column(Integer)
    projectlist_po_state: Mapped[Optional[str]] = mapped_column(String(20))
    selected_rows: Mapped[int] = mapped_column(Integer, default=0)
    ignored_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    skipped_settled: Mapped[int] = mapped_column(Integer, default=0)
    source_conflicts: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True,
    )


class POImportRowLog(Base):
    __tablename__ = "po_import_row_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('imported', 'skip_duplicate', 'skip_settled', "
            "'source_conflict', 'invalid', 'ignored')",
            name="ck_po_import_row_logs_action",
        ),
        UniqueConstraint(
            "batch_id", "sheet", "source_row",
            name="uq_po_import_row_logs_batch_sheet_row",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("po_import_batches.id"),
        index=True,
    )
    sheet: Mapped[str] = mapped_column(String(255))
    source_row: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30), index=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    po_id: Mapped[Optional[int]] = mapped_column(Integer)
    translator_id: Mapped[Optional[int]] = mapped_column(Integer)
    translator_name: Mapped[Optional[str]] = mapped_column(String(200))
    project: Mapped[Optional[str]] = mapped_column(String(200))
    settlement_month: Mapped[Optional[str]] = mapped_column(String(7))
    role: Mapped[Optional[str]] = mapped_column(String(50))
    source_lang: Mapped[Optional[str]] = mapped_column(String(20))
    target_lang: Mapped[Optional[str]] = mapped_column(String(20))
    pricing_mode: Mapped[Optional[str]] = mapped_column(String(20))
    word_count: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 6))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    source_fee_cny: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    source_key: Mapped[Optional[str]] = mapped_column(String(64))
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))
    contract_type: Mapped[Optional[str]] = mapped_column(String(50))
    sign_date: Mapped[Optional[str]] = mapped_column(String(20))
    expiry_date: Mapped[Optional[str]] = mapped_column(String(20))
    nda_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    nda_expiry: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[Optional[str]] = mapped_column(String(20))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id,
                "contract_number": self.contract_number, "contract_type": self.contract_type,
                "sign_date": self.sign_date, "expiry_date": self.expiry_date,
                "nda_signed": self.nda_signed, "nda_expiry": self.nda_expiry,
                "status": self.status, "remarks": self.remarks}


class QualityScore(Base):
    __tablename__ = "quality_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    evaluation_period: Mapped[Optional[str]] = mapped_column(String(20))
    project: Mapped[Optional[str]] = mapped_column(String(200))
    qa_type: Mapped[Optional[str]] = mapped_column(String(50))
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    critical_errors: Mapped[int] = mapped_column(Integer, default=0)
    major_errors: Mapped[int] = mapped_column(Integer, default=0)
    minor_errors: Mapped[int] = mapped_column(Integer, default=0)
    is_qualified: Mapped[Optional[bool]] = mapped_column(Boolean)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    reviewer: Mapped[Optional[str]] = mapped_column(String(100))
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id,
                "evaluation_period": self.evaluation_period, "project": self.project,
                "qa_type": self.qa_type, "score": _f(self.score),
                "critical_errors": self.critical_errors, "major_errors": self.major_errors,
                "minor_errors": self.minor_errors, "is_qualified": self.is_qualified,
                "failure_reason": self.failure_reason, "reviewer": self.reviewer,
                "feedback_notes": self.feedback_notes}


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    date: Mapped[Optional[str]] = mapped_column(String(20))
    project: Mapped[Optional[str]] = mapped_column(String(200))
    complaint_type: Mapped[Optional[str]] = mapped_column(String(50))
    severity: Mapped[Optional[str]] = mapped_column(String(20))
    deduction_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    resolution: Mapped[Optional[str]] = mapped_column(String(50))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id, "date": self.date,
                "project": self.project, "complaint_type": self.complaint_type,
                "severity": self.severity,
                "deduction_amount": _f(self.deduction_amount),
                "resolution": self.resolution, "remarks": self.remarks}


class CapacityMonthOverride(Base):
    __tablename__ = "capacity_month_overrides"
    __table_args__ = (
        UniqueConstraint(
            "translator_id",
            "month",
            name="uq_capacity_month_overrides_translator_month",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[Optional[str]] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def as_dict(self):
        return {
            "id": self.id,
            "translator_id": self.translator_id,
            "month": self.month,
            "status": self.status,
            "reason": self.reason,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            if self.updated_at else None,
        }


class PaymentInfo(Base):
    __tablename__ = "payment_infos"
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), primary_key=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    bank_name: Mapped[Optional[str]] = mapped_column(String(200))
    bank_account_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    id_card_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    payee_name: Mapped[Optional[str]] = mapped_column(String(100))
    supports_wechat: Mapped[bool] = mapped_column(Boolean, default=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self, reveal=False):
        ba = dec(self.bank_account_enc)
        ic = dec(self.id_card_enc)
        return {"translator_id": self.translator_id, "currency": self.currency,
                "bank_name": self.bank_name,
                "bank_account": ba if reveal else mask(ba),
                "id_card": ic if reveal else mask(ic),
                "payee_name": self.payee_name, "supports_wechat": self.supports_wechat,
                "remarks": self.remarks}


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    method: Mapped[str] = mapped_column(String(30), index=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    account_name: Mapped[Optional[str]] = mapped_column(String(100))
    account_number_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    bank_name: Mapped[Optional[str]] = mapped_column(String(200))
    bank_address: Mapped[Optional[str]] = mapped_column(String(300))
    swift_code: Mapped[Optional[str]] = mapped_column(String(50))
    routing_code: Mapped[Optional[str]] = mapped_column(String(50))
    tax_id_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    qr_stored_name: Mapped[Optional[str]] = mapped_column(String(120))
    qr_original_name: Mapped[Optional[str]] = mapped_column(String(255))
    qr_mime: Mapped[Optional[str]] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self, reveal=False):
        account_number = dec(self.account_number_enc)
        tax_id = dec(self.tax_id_enc)
        return {
            "id": self.id,
            "translator_id": self.translator_id,
            "method": self.method,
            "currency": self.currency,
            "account_name": self.account_name,
            "account_number": account_number if reveal else mask(account_number),
            "bank_name": self.bank_name,
            "bank_address": self.bank_address,
            "swift_code": self.swift_code,
            "routing_code": self.routing_code,
            "tax_id": tax_id if reveal else mask(tax_id),
            "has_qr": bool(self.qr_stored_name),
            "qr_original_name": self.qr_original_name,
            "is_default": self.is_default,
            "remarks": self.remarks,
        }


class LanguagePair(Base):
    __tablename__ = "language_pairs"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    source_lang: Mapped[str] = mapped_column(String(20))
    target_lang: Mapped[str] = mapped_column(String(20))
    translation_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    mtpe_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    review_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    lqa_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    lqe_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    rate_confirmed_date: Mapped[Optional[str]] = mapped_column(String(20))

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id,
                "source_lang": self.source_lang, "target_lang": self.target_lang,
                "translation_rate": _f(self.translation_rate), "mtpe_rate": _f(self.mtpe_rate),
                "review_rate": _f(self.review_rate), "lqa_rate": _f(self.lqa_rate),
                "lqe_rate": _f(self.lqe_rate), "currency": self.currency,
                "rate_confirmed_date": self.rate_confirmed_date}


class ProjectPrice(Base):
    __tablename__ = "project_prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    project_experience_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("translator_project_experiences.id")
    )
    project_name: Mapped[str] = mapped_column(String(200))
    source_lang: Mapped[Optional[str]] = mapped_column(String(20))
    target_lang: Mapped[Optional[str]] = mapped_column(String(20))
    price_type: Mapped[str] = mapped_column(String(20), index=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(50))
    custom_task_name: Mapped[Optional[str]] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    unit: Mapped[str] = mapped_column(String(30))
    currency: Mapped[str] = mapped_column(String(10))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {
            "id": self.id,
            "translator_id": self.translator_id,
            "project_experience_id": self.project_experience_id,
            "project_name": self.project_name,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "price_type": self.price_type,
            "task_type": self.task_type,
            "custom_task_name": self.custom_task_name,
            "amount": _f(self.amount),
            "unit": self.unit,
            "currency": self.currency,
            "remarks": self.remarks,
        }


class TranslatorAttachment(Base):
    __tablename__ = "translator_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(120), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def as_dict(self):
        return {
            "id": self.id,
            "translator_id": self.translator_id,
            "category": self.category,
            "original_name": self.original_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if self.created_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped[Optional[str]] = mapped_column(String(50))
    action: Mapped[Optional[str]] = mapped_column(String(20))
    entity: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def as_dict(self):
        return {"id": self.id, "user": self.user, "action": self.action, "entity": self.entity,
                "entity_id": self.entity_id, "detail": self.detail,
                "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None}


class PendingChange(Base):
    __tablename__ = "pending_changes"
    __table_args__ = (
        Index("ux_pending_actor_idempotency", "created_by", "idempotency_key",
              unique=True, sqlite_where=text("idempotency_key IS NOT NULL")),
        Index("ux_pending_active_fingerprint", "payload_hash", unique=True,
              sqlite_where=text("status = 'pending' AND payload_hash IS NOT NULL")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(50))
    kind: Mapped[Optional[str]] = mapped_column(String(30))
    translator_id: Mapped[Optional[int]] = mapped_column(Integer)
    payload: Mapped[Optional[str]] = mapped_column(Text)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(160))
    request_hash: Mapped[Optional[str]] = mapped_column(String(64))
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class PendingIdempotency(Base):
    __tablename__ = "pending_idempotency"
    __table_args__ = (UniqueConstraint("created_by", "idempotency_key",
                                       name="uq_pending_idempotency_actor_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[Optional[str]] = mapped_column(String(64))
    pending_change_id: Mapped[int] = mapped_column(ForeignKey("pending_changes.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
