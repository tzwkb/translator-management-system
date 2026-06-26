"""SQLAlchemy 数据模型（11 张表）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer,
                        LargeBinary, Numeric, String, Text)
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
    weekend_off: Mapped[Optional[bool]] = mapped_column(Boolean)
    availability: Mapped[Optional[str]] = mapped_column(String(50))
    cumulative_word_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # 财务信息
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
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
                "onboarding_date", "status", "source", "language_pairs", "translation_rate",
                "mtpe_rate", "review_rate", "lqa_rate", "rate_confirmed_date", "domains",
                "text_types", "cat_tools", "internal_rating", "trial_result", "current_project",
                "role", "daily_output", "weekend_off", "availability", "currency",
                "payment_method", "invoice_type", "tax_deduction", "contract_status",
                "contract_expiry", "nda_signed", "punctuality_rate", "responsiveness",
                "cooperation_rating", "last_contact", "remarks")
    # 系统自动算字段（联动维护，只读）
    DERIVED = ("recent_qa_score", "cumulative_qa_score", "low_error_count", "low_error_rate",
               "complaint_count", "deduction_total", "negotiation_status", "last_negotiation_date",
               "post_negotiation_rate", "rate_reduction_pct", "accepted_reduction",
               "negotiation_notes", "cumulative_unpaid", "cumulative_word_count")

    def as_dict(self):
        return {
            "id": self.id, "name": self.name, "wechat": self.wechat, "email": self.email,
            "location": self.location, "timezone": self.timezone,
            "native_language": self.native_language, "onboarding_date": self.onboarding_date,
            "status": self.status, "source": self.source,
            "language_pairs": self.language_pairs, "translation_rate": _f(self.translation_rate),
            "mtpe_rate": _f(self.mtpe_rate), "review_rate": _f(self.review_rate),
            "lqa_rate": _f(self.lqa_rate), "rate_confirmed_date": self.rate_confirmed_date,
            "domains": self.domains, "text_types": self.text_types, "cat_tools": self.cat_tools,
            "internal_rating": self.internal_rating, "trial_result": self.trial_result,
            "recent_qa_score": _f(self.recent_qa_score),
            "cumulative_qa_score": _f(self.cumulative_qa_score),
            "low_error_count": self.low_error_count, "low_error_rate": _f(self.low_error_rate),
            "current_project": self.current_project, "role": self.role,
            "daily_output": self.daily_output, "weekend_off": self.weekend_off,
            "availability": self.availability, "cumulative_word_count": self.cumulative_word_count,
            "currency": self.currency, "payment_method": self.payment_method,
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
        }


class RateChange(Base):
    __tablename__ = "rate_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    change_date: Mapped[str] = mapped_column(String(20))
    task_type: Mapped[Optional[str]] = mapped_column(String(50))
    original_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    new_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    negotiator: Mapped[Optional[str]] = mapped_column(String(100))
    reason: Mapped[Optional[str]] = mapped_column(String(100))
    result: Mapped[Optional[str]] = mapped_column(String(20))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id, "change_date": self.change_date,
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
    role: Mapped[Optional[str]] = mapped_column(String(50))
    word_count: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    status: Mapped[str] = mapped_column(String(20), default="未开票", index=True)
    po_number: Mapped[Optional[str]] = mapped_column(String(50))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id,
                "settlement_month": self.settlement_month, "project": self.project, "role": self.role,
                "word_count": _f(self.word_count), "rate": _f(self.rate), "amount": _f(self.amount),
                "currency": self.currency, "status": self.status, "po_number": self.po_number,
                "remarks": self.remarks}


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
    reviewer: Mapped[Optional[str]] = mapped_column(String(100))
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id,
                "evaluation_period": self.evaluation_period, "project": self.project,
                "qa_type": self.qa_type, "score": _f(self.score),
                "critical_errors": self.critical_errors, "major_errors": self.major_errors,
                "minor_errors": self.minor_errors, "reviewer": self.reviewer,
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


class Capacity(Base):
    __tablename__ = "capacity_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    translator_id: Mapped[int] = mapped_column(ForeignKey("translators.id"), index=True)
    period_year: Mapped[int] = mapped_column(Integer)
    period_month: Mapped[int] = mapped_column(Integer)
    week_no: Mapped[int] = mapped_column(Integer)
    project: Mapped[Optional[str]] = mapped_column(String(200))
    occupancy_pct: Mapped[int] = mapped_column(Integer, default=0)

    def as_dict(self):
        return {"id": self.id, "translator_id": self.translator_id, "period_year": self.period_year,
                "period_month": self.period_month, "week_no": self.week_no, "project": self.project,
                "occupancy_pct": self.occupancy_pct}


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
    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(50))
    kind: Mapped[Optional[str]] = mapped_column(String(30))
    translator_id: Mapped[Optional[int]] = mapped_column(Integer)
    payload: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
