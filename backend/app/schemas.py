"""Pydantic 请求体（校验进来的数据格式）。"""
import re
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Currency = Literal["CNY", "USD", "EUR"]
TaskType = Literal["翻译", "审校", "MTPE", "LQA", "LQE", "其他"]
POStatus = Literal["未开票", "已开票待付", "已支付", "有争议"]


def _blank(v: Any):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return v


def _date(v: Any, *, required: bool = False):
    v = _blank(v)
    if v is None:
        if required:
            raise ValueError("日期必填")
        return None
    s = str(v).strip()
    if not DATE_RE.fullmatch(s):
        raise ValueError("日期格式应为 YYYY-MM-DD")
    try:
        date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError("日期不存在") from exc
    return s


def _month(v: Any, *, required: bool = False):
    v = _blank(v)
    if v is None:
        if required:
            raise ValueError("月份必填")
        return None
    s = str(v).strip()
    if not MONTH_RE.fullmatch(s):
        raise ValueError("月份格式应为 YYYY-MM")
    y, m = s.split("-")
    if not (1 <= int(m) <= 12):
        raise ValueError("月份不存在")
    return f"{int(y):04d}-{int(m):02d}"


def _non_negative(v: Any):
    if v is not None and v < 0:
        raise ValueError("数值不能为负")
    return v


def _percent(v: Any):
    if v is not None and not (0 <= v <= 100):
        raise ValueError("百分比应在 0-100")
    return v


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
    internal_rating: Optional[Literal["S", "A", "B", "C", "D"]] = None
    trial_result: Optional[Literal["Pass", "Fail", "Pending"]] = None
    current_project: Optional[str] = None
    role: Optional[TaskType] = None
    daily_output: Optional[int] = None
    weekend_off: Optional[bool] = None
    availability: Optional[Literal["空闲", "部分空闲", "满负荷"]] = None
    currency: Optional[Currency] = None
    payment_method: Optional[str] = None
    invoice_type: Optional[str] = None
    tax_deduction: Optional[str] = None
    contract_status: Optional[Literal["有效", "即将到期", "已过期", "无合同"]] = None
    contract_expiry: Optional[str] = None
    nda_signed: Optional[bool] = None
    punctuality_rate: Optional[float] = None
    responsiveness: Optional[Literal["快", "一般", "慢"]] = None
    cooperation_rating: Optional[Literal["优先合作", "正常合作", "谨慎合作", "停止合作"]] = None
    last_contact: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("onboarding_date", mode="before")
    @classmethod
    def valid_onboarding_date(cls, v):
        return _date(v, required=True)

    @field_validator("rate_confirmed_date", "contract_expiry", "last_contact", mode="before")
    @classmethod
    def valid_optional_dates(cls, v):
        return _date(v)

    @field_validator("email", mode="before")
    @classmethod
    def valid_email(cls, v):
        v = _blank(v)
        if v is not None and not EMAIL_RE.fullmatch(str(v)):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("translation_rate", "mtpe_rate", "review_rate", "lqa_rate", "daily_output")
    @classmethod
    def non_negative_numbers(cls, v):
        return _non_negative(v)

    @field_validator("punctuality_rate")
    @classmethod
    def valid_punctuality(cls, v):
        return _percent(v)


class RateChangeIn(BaseModel):
    change_date: str
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None
    task_type: Optional[TaskType] = None
    original_rate: Optional[float] = None
    new_rate: Optional[float] = None
    currency: Optional[Currency] = None
    negotiator: Optional[str] = None
    reason: Optional[str] = None
    result: Optional[Literal["进行中", "成功", "拒绝"]] = "成功"          # 成功才同步主表谈判字段
    remarks: Optional[str] = None

    @field_validator("change_date", mode="before")
    @classmethod
    def valid_change_date(cls, v):
        return _date(v, required=True)

    @field_validator("original_rate", "new_rate")
    @classmethod
    def valid_rates(cls, v):
        return _non_negative(v)


class POIn(BaseModel):
    translator_id: int
    settlement_month: str
    project: Optional[str] = None
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None
    role: Optional[TaskType] = None
    word_count: Optional[float] = None
    rate: Optional[float] = None
    currency: Currency = "CNY"
    status: POStatus = "未开票"
    po_number: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("settlement_month", mode="before")
    @classmethod
    def valid_settlement_month(cls, v):
        return _month(v, required=True)

    @field_validator("word_count", "rate")
    @classmethod
    def valid_amount_fields(cls, v):
        return _non_negative(v)


class StatusIn(BaseModel):
    status: str


class LanguagePairIn(BaseModel):
    source_lang: str
    target_lang: str
    translation_rate: Optional[float] = None
    mtpe_rate: Optional[float] = None
    review_rate: Optional[float] = None
    lqa_rate: Optional[float] = None
    lqe_rate: Optional[float] = None
    currency: Optional[Currency] = None
    rate_confirmed_date: Optional[str] = None

    @field_validator("rate_confirmed_date", mode="before")
    @classmethod
    def valid_rate_confirmed_date(cls, v):
        return _date(v)

    @field_validator("translation_rate", "mtpe_rate", "review_rate", "lqa_rate", "lqe_rate")
    @classmethod
    def valid_rates(cls, v):
        return _non_negative(v)


class ContractIn(BaseModel):
    contract_number: Optional[str] = None
    contract_type: Optional[Literal["框架协议", "单项目合同", "试用合同", "兼职协议"]] = None
    sign_date: Optional[str] = None
    expiry_date: Optional[str] = None
    nda_signed: bool = False
    nda_expiry: Optional[str] = None
    status: Optional[Literal["有效", "即将到期", "已过期", "无合同"]] = None
    remarks: Optional[str] = None

    @field_validator("sign_date", "expiry_date", "nda_expiry", mode="before")
    @classmethod
    def valid_contract_dates(cls, v):
        return _date(v)


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

    @field_validator("evaluation_period", mode="before")
    @classmethod
    def valid_evaluation_period(cls, v):
        return _month(v)

    @field_validator("score")
    @classmethod
    def valid_score(cls, v):
        return _percent(v)

    @field_validator("critical_errors", "major_errors", "minor_errors")
    @classmethod
    def valid_error_counts(cls, v):
        return _non_negative(v)


class ComplaintIn(BaseModel):
    date: Optional[str] = None
    project: Optional[str] = None
    complaint_type: Optional[str] = None
    severity: Optional[Literal["轻微", "一般", "严重", "极严重"]] = None
    deduction_amount: Optional[float] = None
    resolution: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("date", mode="before")
    @classmethod
    def valid_complaint_date(cls, v):
        return _date(v)

    @field_validator("deduction_amount")
    @classmethod
    def valid_deduction_amount(cls, v):
        return _non_negative(v)


class CapacityIn(BaseModel):
    period_year: int
    period_month: int
    week_no: int
    project: Optional[str] = None
    occupancy_pct: int = 0

    @field_validator("period_year")
    @classmethod
    def valid_period_year(cls, v):
        if not (1900 <= v <= 2100):
            raise ValueError("年份应在 1900-2100")
        return v

    @field_validator("period_month")
    @classmethod
    def valid_period_month(cls, v):
        if not (1 <= v <= 12):
            raise ValueError("月份应在 1-12")
        return v

    @field_validator("week_no")
    @classmethod
    def valid_week_no(cls, v):
        if not (1 <= v <= 6):
            raise ValueError("周次应在 1-6")
        return v

    @field_validator("occupancy_pct")
    @classmethod
    def valid_occupancy(cls, v):
        return _percent(v)


class PaymentIn(BaseModel):
    currency: Optional[Currency] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    id_card: Optional[str] = None
    payee_name: Optional[str] = None
    supports_wechat: bool = False
    remarks: Optional[str] = None


class LoginIn(BaseModel):
    user: str
