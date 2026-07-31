"""Generic AND filters for translator master and related business records."""
import json
import re

from fastapi import HTTPException
from sqlalchemy import select

from .models import (
    Capacity,
    Complaint,
    Contract,
    LanguagePair,
    PaymentAccount,
    PO,
    ProjectPrice,
    QualityScore,
    RateChange,
    TranslatorAttachment,
    TranslatorAlias,
    TranslatorProjectExperience,
)


_MAIN_FIELDS = [
    ("id", "译员ID", "number"),
    ("name", "姓名", "text"),
    ("wechat", "微信", "text"),
    ("email", "邮箱", "text"),
    ("location", "所在地", "text"),
    ("timezone", "时区", "text"),
    ("native_language", "母语", "text"),
    ("onboarding_date", "入库日期", "date"),
    ("status", "状态", "text"),
    ("source", "来源", "text"),
    ("gender", "性别", "text"),
    ("entity_type", "主体类型", "text"),
    ("language_pairs", "语言对摘要", "text"),
    ("domains", "擅长领域", "text"),
    ("text_types", "文本类型", "text"),
    ("cat_tools", "CAT工具", "text"),
    ("internal_rating", "当前质量等级", "text"),
    ("manual_rating", "人工质量等级", "text"),
    ("manual_rating_reason", "人工评级原因", "text"),
    ("trial_result", "试译结果", "text"),
    ("current_project", "旧当前项目", "text"),
    ("role", "旧当前角色", "text"),
    ("daily_output", "翻译日产量", "number"),
    ("weekend_off", "是否双休", "boolean"),
    ("availability", "人工产能状态", "text"),
    ("computed_availability", "计算产能状态", "text"),
    ("computed_load_pct", "计算占用率", "number"),
    ("cumulative_word_count", "累计字数", "number"),
    ("currency", "结算币种", "text"),
    ("payment_method", "旧支付方式", "text"),
    ("settlement_mode", "结算策略", "text"),
    ("invoice_type", "开票类型", "text"),
    ("tax_deduction", "扣税方式", "text"),
    ("cumulative_unpaid", "累计未付", "number"),
    ("contract_status", "合同状态", "text"),
    ("contract_expiry", "合同到期", "date"),
    ("nda_signed", "NDA签署", "boolean"),
    ("punctuality_rate", "准时率", "number"),
    ("responsiveness", "响应速度", "text"),
    ("cooperation_rating", "合作评级", "text"),
    ("last_contact", "最近联系", "date"),
    ("complaint_count", "客诉次数", "number"),
    ("deduction_total", "累计扣款", "number"),
    ("remarks", "译员备注", "text"),
]

_RELATED_FIELDS = {
    "aliases": [
        ("alias", "名称映射·别名", "text"),
    ],
    "projects": [
        ("cooperation_source", "项目·合作来源", "text"),
        ("project_status", "项目·状态", "text"),
        ("project_name", "项目·名称", "text"),
        ("external_company", "项目·外部公司", "text"),
        ("role", "项目·角色", "text"),
        ("source_lang", "项目·源语言", "text"),
        ("target_lang", "项目·目标语言", "text"),
        ("start_date", "项目·开始日期", "date"),
        ("end_date", "项目·结束日期", "date"),
        ("remaining_volume", "项目·剩余量", "number"),
        ("deadline", "项目·截止日", "date"),
        ("remarks", "项目·备注", "text"),
    ],
    "language_pairs": [
        ("source_lang", "语言对·源语言", "text"),
        ("target_lang", "语言对·目标语言", "text"),
        ("translation_rate", "语言对·翻译价格", "number"),
        ("mtpe_rate", "语言对·MTPE价格", "number"),
        ("review_rate", "语言对·审校价格", "number"),
        ("lqa_rate", "语言对·LQA价格", "number"),
        ("lqe_rate", "语言对·LQE价格", "number"),
        ("currency", "语言对·币种", "text"),
        ("rate_confirmed_date", "语言对·价格确认日", "date"),
    ],
    "project_prices": [
        ("project_name", "项目价格·项目", "text"),
        ("price_type", "项目价格·类型", "text"),
        ("task_type", "项目价格·任务", "text"),
        ("custom_task_name", "项目价格·自定义任务", "text"),
        ("amount", "项目价格·金额", "number"),
        ("unit", "项目价格·单位", "text"),
        ("currency", "项目价格·币种", "text"),
        ("remarks", "项目价格·备注", "text"),
    ],
    "rate_changes": [
        ("change_date", "调价·日期", "date"),
        ("task_type", "调价·任务", "text"),
        ("original_rate", "调价·原价", "number"),
        ("new_rate", "调价·新价", "number"),
        ("negotiator", "调价·谈价人", "text"),
        ("reason", "调价·原因", "text"),
        ("result", "调价·结果", "text"),
    ],
    "quality": [
        ("evaluation_period", "质量·周期", "date"),
        ("project", "质量·项目", "text"),
        ("qa_type", "质量·类型", "text"),
        ("score", "质量·LQE分", "number"),
        ("is_qualified", "质量·是否合格", "boolean"),
        ("failure_reason", "质量·不合格原因", "text"),
        ("reviewer", "质量·评审人", "text"),
    ],
    "contracts": [
        ("contract_number", "合同·编号", "text"),
        ("contract_type", "合同·类型", "text"),
        ("sign_date", "合同·签署日", "date"),
        ("expiry_date", "合同·到期日", "date"),
        ("nda_signed", "合同·NDA", "boolean"),
        ("status", "合同·状态", "text"),
    ],
    "complaints": [
        ("date", "客诉·日期", "date"),
        ("project", "客诉·项目", "text"),
        ("complaint_type", "客诉·类型", "text"),
        ("severity", "客诉·严重度", "text"),
        ("deduction_amount", "客诉·扣款", "number"),
        ("resolution", "客诉·处理结果", "text"),
    ],
    "capacity": [
        ("period_year", "旧产能·年份", "number"),
        ("period_month", "旧产能·月份", "number"),
        ("week_no", "旧产能·周次", "number"),
        ("project", "旧产能·项目", "text"),
        ("occupancy_pct", "旧产能·占用率", "number"),
    ],
    "payments": [
        ("method", "支付·方式", "text"),
        ("currency", "支付·币种", "text"),
        ("account_name", "支付·账户名", "text"),
        ("bank_name", "支付·银行", "text"),
        ("bank_address", "支付·银行地址", "text"),
        ("swift_code", "支付·SWIFT", "text"),
        ("routing_code", "支付·路由号", "text"),
        ("has_account_number", "支付·有账号", "boolean"),
        ("has_tax_id", "支付·有税号", "boolean"),
        ("has_qr", "支付·有收款码", "boolean"),
        ("remarks", "支付·备注", "text"),
    ],
    "attachments": [
        ("category", "附件·分类", "text"),
        ("original_name", "附件·文件名", "text"),
        ("mime_type", "附件·MIME", "text"),
        ("size_bytes", "附件·大小", "number"),
        ("created_at", "附件·上传时间", "date"),
    ],
    "po": [
        ("settlement_month", "PO·结算月", "date"),
        ("project", "PO·项目", "text"),
        ("role", "PO·角色", "text"),
        ("source_lang", "PO·源语言", "text"),
        ("target_lang", "PO·目标语言", "text"),
        ("word_count", "PO·数量", "number"),
        ("rate", "PO·单价", "number"),
        ("amount", "PO·金额", "number"),
        ("currency", "PO·币种", "text"),
        ("status", "PO·状态", "text"),
        ("po_number", "PO·编号", "text"),
        ("pricing_mode", "PO·计价模式", "text"),
        ("remarks", "PO·备注", "text"),
    ],
}

FILTER_FIELDS = [
    {"field": field, "label": label, "kind": kind}
    for field, label, kind in _MAIN_FIELDS
]
for prefix, fields in _RELATED_FIELDS.items():
    FILTER_FIELDS.extend(
        {
            "field": f"{prefix}.{field}",
            "label": label,
            "kind": kind,
        }
        for field, label, kind in fields
    )

_FIELD_KINDS = {item["field"]: item["kind"] for item in FILTER_FIELDS}
_OPS = {"contains", "eq", "in", "gte", "lte", "between", "empty", "not_empty"}
_RELATED_MODELS = {
    "aliases": TranslatorAlias,
    "projects": TranslatorProjectExperience,
    "language_pairs": LanguagePair,
    "project_prices": ProjectPrice,
    "rate_changes": RateChange,
    "quality": QualityScore,
    "contracts": Contract,
    "complaints": Complaint,
    "capacity": Capacity,
    "payments": PaymentAccount,
    "attachments": TranslatorAttachment,
    "po": PO,
}


def parse_filter_conditions(raw):
    if not raw:
        return []
    try:
        conditions = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise HTTPException(400, "全部字段筛选格式非法") from error
    if not isinstance(conditions, list) or len(conditions) > 20:
        raise HTTPException(400, "全部字段筛选必须是最多 20 条条件的数组")
    parsed = []
    for condition in conditions:
        if not isinstance(condition, dict):
            raise HTTPException(400, "筛选条件格式非法")
        field = condition.get("field")
        op = condition.get("op", "contains")
        if field not in _FIELD_KINDS:
            raise HTTPException(400, f"不支持筛选字段：{field}")
        if op not in _OPS:
            raise HTTPException(400, f"不支持筛选方式：{op}")
        value = condition.get("value")
        if op not in {"empty", "not_empty"} and (value is None or value == ""):
            raise HTTPException(400, "筛选值不能为空")
        parsed.append({
            "field": field,
            "op": op,
            "value": condition.get("value"),
            "kind": _FIELD_KINDS[field],
        })
    return parsed


def load_related_filter_rows(session, translator_ids):
    context = {tid: {} for tid in translator_ids}
    if not translator_ids:
        return context
    for prefix, model in _RELATED_MODELS.items():
        rows = session.scalars(
            select(model).where(model.translator_id.in_(translator_ids))
        ).all()
        for row in rows:
            data = row.as_dict()
            if prefix == "payments":
                data["has_account_number"] = bool(row.account_number_enc)
                data["has_tax_id"] = bool(row.tax_id_enc)
            context.setdefault(row.translator_id, {}).setdefault(prefix, []).append(data)
    return context


def _present(value):
    return value is not None and str(value).strip() != ""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().casefold()


def _split_values(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        item.strip()
        for item in re.split(r"[,，;；]", str(value))
        if item.strip()
    ]


def _matches_value(value, condition):
    op = condition["op"]
    target = condition.get("value")
    kind = condition["kind"]
    if kind == "number":
        actual_number = _number(value)
        if actual_number is None:
            return False
        if op == "between":
            bounds = _split_values(target)
            return (
                len(bounds) == 2
                and _number(bounds[0]) is not None
                and _number(bounds[1]) is not None
                and _number(bounds[0]) <= actual_number <= _number(bounds[1])
            )
        target_number = _number(target)
        if target_number is None:
            return False
        return {
            "eq": actual_number == target_number,
            "gte": actual_number >= target_number,
            "lte": actual_number <= target_number,
        }.get(op, str(target_number) in str(actual_number))
    actual = _bool_text(value) if kind == "boolean" else str(value).strip().casefold()
    if op == "in":
        return actual in {item.casefold() for item in _split_values(target)}
    expected = _bool_text(target) if kind == "boolean" else str(target).strip().casefold()
    if op == "eq":
        return actual == expected
    if op == "gte":
        return actual >= expected
    if op == "lte":
        return actual <= expected
    if op == "between":
        bounds = _split_values(target)
        return len(bounds) == 2 and bounds[0].casefold() <= actual <= bounds[1].casefold()
    return expected in actual


def matches_filter_conditions(translator_data, related_rows, conditions):
    for condition in conditions:
        field = condition["field"]
        if "." in field:
            prefix, key = field.split(".", 1)
            values = [
                row.get(key)
                for row in related_rows.get(prefix, [])
            ]
        else:
            values = [translator_data.get(field)]
        present = [value for value in values if _present(value)]
        if condition["op"] == "empty":
            matched = not present
        elif condition["op"] == "not_empty":
            matched = bool(present)
        else:
            matched = any(_matches_value(value, condition) for value in present)
        if not matched:
            return False
    return True
