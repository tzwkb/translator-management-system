"""Pydantic 请求体（校验进来的数据格式）。"""
from typing import Literal, Optional

from pydantic import BaseModel


class TranslatorIn(BaseModel):
    # 仅人录入字段；派生字段（QA分/客诉数/谈判/累计等）由联动维护，不在此
    name: str
    native_language: str                  # PRD 必填
    onboarding_date: str                  # PRD 必填
    email: Optional[str] = None
    wechat: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    status: Literal["Active", "Dormant", "Blacklisted", "Probation"] = "Active"
    source: Optional[str] = None
    language_pairs: Optional[str] = None
    translation_rate: Optional[float] = None
    mtpe_rate: Optional[float] = None
    review_rate: Optional[float] = None
    lqa_rate: Optional[float] = None
    rate_confirmed_date: Optional[str] = None
    domains: Optional[str] = None
    text_types: Optional[str] = None
    cat_tools: Optional[str] = None
    internal_rating: Optional[str] = None
    trial_result: Optional[str] = None
    current_project: Optional[str] = None
    role: Optional[str] = None
    daily_output: Optional[int] = None
    weekend_off: Optional[bool] = None
    availability: Optional[str] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    invoice_type: Optional[str] = None
    tax_deduction: Optional[str] = None
    contract_status: Optional[str] = None
    contract_expiry: Optional[str] = None
    nda_signed: Optional[bool] = None
    punctuality_rate: Optional[float] = None
    responsiveness: Optional[str] = None
    cooperation_rating: Optional[str] = None
    last_contact: Optional[str] = None
    remarks: Optional[str] = None


class RateChangeIn(BaseModel):
    change_date: str
    task_type: Optional[str] = None
    original_rate: Optional[float] = None
    new_rate: Optional[float] = None
    negotiator: Optional[str] = None
    reason: Optional[str] = None
    result: Optional[str] = "成功"          # 进行中/成功/拒绝；成功才同步主表谈判字段
    remarks: Optional[str] = None


class POIn(BaseModel):
    translator_id: int
    settlement_month: str
    project: Optional[str] = None
    role: Optional[str] = None
    word_count: Optional[float] = None
    rate: Optional[float] = None
    currency: str = "CNY"
    status: str = "未开票"
    po_number: Optional[str] = None
    remarks: Optional[str] = None


class StatusIn(BaseModel):
    status: str


class ContractIn(BaseModel):
    contract_number: Optional[str] = None
    contract_type: Optional[str] = None
    sign_date: Optional[str] = None
    expiry_date: Optional[str] = None
    nda_signed: bool = False
    nda_expiry: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class QualityIn(BaseModel):
    evaluation_period: Optional[str] = None
    project: Optional[str] = None
    qa_type: Optional[str] = None
    score: Optional[float] = None
    critical_errors: int = 0
    major_errors: int = 0
    minor_errors: int = 0
    reviewer: Optional[str] = None
    feedback_notes: Optional[str] = None


class ComplaintIn(BaseModel):
    date: Optional[str] = None
    project: Optional[str] = None
    complaint_type: Optional[str] = None
    severity: Optional[Literal["轻微", "一般", "严重", "极严重"]] = None
    deduction_amount: Optional[float] = None
    resolution: Optional[str] = None
    remarks: Optional[str] = None


class CapacityIn(BaseModel):
    period_year: int
    period_month: int
    week_no: int
    project: Optional[str] = None
    occupancy_pct: int = 0


class PaymentIn(BaseModel):
    currency: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    id_card: Optional[str] = None
    payee_name: Optional[str] = None
    supports_wechat: bool = False
    remarks: Optional[str] = None


class LoginIn(BaseModel):
    user: str
