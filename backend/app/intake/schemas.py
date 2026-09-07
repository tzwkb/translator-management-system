from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..schemas import Currency, EMAIL_RE, ProjectExperienceIn, _date
from ..services import LANGUAGE_SET


class IntakeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class InviteIn(IntakeModel):
    email: str = Field(min_length=3, max_length=200)
    translator_id: int | None = Field(default=None, gt=0)
    expires_days: int = Field(default=14, ge=1, le=30)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("邮箱格式无效 / Invalid email address")
        return value.lower()


Rate = Annotated[float, Field(ge=0, le=99999999.99)]


class IntakeLanguagePair(IntakeModel):
    source_lang: str = Field(min_length=2, max_length=20)
    target_lang: str = Field(min_length=2, max_length=20)
    translation_rate: Rate | None = None
    review_rate: Rate | None = None
    mtpe_rate: Rate | None = None
    lqa_rate: Rate | None = None
    lqe_rate: Rate | None = None
    currency: Currency | None = None

    @field_validator("source_lang", "target_lang")
    @classmethod
    def valid_language(cls, value):
        value = value.upper()
        if value not in LANGUAGE_SET:
            raise ValueError("请选择列表中的语言 / Select a listed language")
        return value

    @model_validator(mode="after")
    def valid_pair(self):
        if self.source_lang == self.target_lang:
            raise ValueError("源语言与目标语言不能相同 / Source and target must differ")
        if any(getattr(self, field) is not None for field in RATE_FIELDS) and not self.currency:
            raise ValueError("填写报价时请选择币种 / Select a currency for your rates")
        return self


RATE_FIELDS = ("translation_rate", "review_rate", "mtpe_rate", "lqa_rate", "lqe_rate")
PROFILE_FIELDS = (
    "name", "email", "native_language", "gender", "entity_type", "wechat",
    "location", "timezone", "domains", "text_types", "cat_tools", "daily_output",
)


class IntakeProject(ProjectExperienceIn):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    project_name: str = Field(min_length=1, max_length=200)
    external_company: str | None = Field(default=None, max_length=200)
    remarks: str | None = Field(default=None, max_length=2000)
    remaining_volume: float | None = Field(default=None, ge=0, le=999999999999.99)

    @field_validator("source_lang", "target_lang")
    @classmethod
    def valid_language(cls, value):
        return IntakeLanguagePair.valid_language(value) if value else None

    @model_validator(mode="after")
    def valid_pair(self):
        if self.source_lang and self.source_lang == self.target_lang and self.role not in {"LQA", "LQE"}:
            raise ValueError("源语言与目标语言不能相同 / Source and target must differ")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期 / End date precedes start date")
        return self


class IntakeIn(IntakeModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    native_language: str = Field(min_length=1, max_length=50)
    gender: Literal["male", "female"]
    entity_type: Literal["individual", "vendor"]
    wechat: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=50)
    domains: str | None = Field(default=None, max_length=2000)
    text_types: str | None = Field(default=None, max_length=2000)
    cat_tools: str | None = Field(default=None, max_length=2000)
    daily_output: int | None = Field(default=None, ge=0, le=1000000)
    remarks: str | None = Field(default=None, max_length=4000)
    language_pairs: list[IntakeLanguagePair] = Field(min_length=1, max_length=20)
    projects: list[IntakeProject] = Field(default_factory=list, max_length=30)
    consent: Literal[True]

    _email = field_validator("email")(InviteIn.valid_email)

    @field_validator("wechat", "location", "timezone", "domains", "text_types", "cat_tools", "remarks", mode="before")
    @classmethod
    def blank_optional(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def unique_pairs(self):
        pairs = {(pair.source_lang, pair.target_lang) for pair in self.language_pairs}
        if len(pairs) != len(self.language_pairs):
            raise ValueError("语言对重复 / Duplicate language pairs")
        return self


class ReviewIn(IntakeModel):
    action: Literal["approve", "needs_info", "reject"]
    version: int = Field(gt=0)
    note: str = Field(default="", max_length=2000)
    target_id: int | None = Field(default=None, gt=0)
    profile_fingerprint: str | None = Field(default=None, max_length=64)
    include_rates: bool = False
    onboarding_date: str | None = None
    status: Literal["Active", "Dormant", "Blacklisted", "Probation"] = "Probation"
    settlement_mode: Literal["monthly", "cumulative"] = "monthly"

    @field_validator("onboarding_date", mode="before")
    @classmethod
    def valid_date(cls, value):
        return _date(value)

    @model_validator(mode="after")
    def require_note(self):
        if self.action in {"needs_info", "reject"} and not self.note:
            raise ValueError("请填写发给译员的处理意见")
        return self
