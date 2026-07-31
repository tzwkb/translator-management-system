"""审计日志、导入导出接口。"""
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import (PO, AuditLog, LanguagePair, QualityScore, Translator,
                      TranslatorAlias, TranslatorProjectExperience)
from ..schemas import POIn, ProjectExperienceIn, TranslatorIn
from ..security import require_editor
from ..services import (LANGUAGE_SET, audit, expected_amount, prepare_po,
                        resync_translator, svc_add_project_experience,
                        svc_create_po)
from ..translator_identity import (
    add_translator_alias,
    assert_name_not_reserved,
    exact_translator_ids_for_name,
    fuzzy_translator_ids_for_name,
    normalize_translator_name,
)

router = APIRouter(prefix="/api")

TR_COLS = ["id"] + list(Translator.EDITABLE) + list(Translator.DERIVED)
PROJECT_EXPORT_COLS = [
    "id", "translator_id", "translator_name", "translator_email",
    "cooperation_source", "project_status", "project_name", "external_company",
    "role", "source_lang", "target_lang", "start_date", "end_date",
    "remaining_volume", "deadline", "remarks",
]
ALIAS_EXPORT_COLS = [
    "id", "translator_id", "translator_name", "translator_email", "alias",
]

# 导入模板字段（人录入项）：(中文表头, 字段, 是否必填, 枚举可选值)
IMPORT_FIELDS = [
    ("姓名", "name", True, None),
    ("母语", "native_language", True, None),
    ("入库日期", "onboarding_date", True, None),
    ("邮箱", "email", False, None),
    ("微信", "wechat", False, None),
    ("所在地", "location", False, None),
    ("时区", "timezone", False, None),
    ("状态", "status", False, ["Active", "Dormant", "Blacklisted", "Probation"]),
    ("来源", "source", False, None),
    ("性别", "gender", True, ["男", "女"]),
    ("主体类型", "entity_type", False, ["个人译员", "供应商"]),
    ("语言对", "language_pairs", False, None),
    ("擅长领域", "domains", False, None),
    ("文本类型", "text_types", False, None),
    ("CAT工具", "cat_tools", False, None),
    ("试译结果", "trial_result", False, ["Pass", "Fail", "Pending"]),
    ("当前项目", "current_project", False, None),
    ("角色", "role", False, ["翻译", "审校", "MTPE", "LQA", "LQE", "一口价", "其他"]),
    ("日产字数", "daily_output", False, None),
    ("结算币种", "currency", False, ["CNY", "USD", "EUR"]),
    ("支付方式", "payment_method", False, None),
    ("结算策略", "settlement_mode", False, ["monthly", "cumulative"]),
    ("开票类型", "invoice_type", False, None),
    ("扣税方式", "tax_deduction", False, None),
    ("合同状态", "contract_status", False, ["有效", "即将到期", "已过期", "无合同"]),
    ("合同到期", "contract_expiry", False, None),
    ("NDA签署", "nda_signed", False, ["是", "否"]),
    ("准时率", "punctuality_rate", False, None),
    ("响应速度", "responsiveness", False, ["快", "一般", "慢"]),
    ("合作评级", "cooperation_rating", False, ["优先合作", "正常合作", "谨慎合作", "停止合作"]),
    ("最近联系", "last_contact", False, None),
    ("备注", "remarks", False, None),
]
_HEADER_MAP = {lbl: f for lbl, f, _, _ in IMPORT_FIELDS}
_HEADER_MAP.update({f: f for _, f, _, _ in IMPORT_FIELDS})   # 英文字段名也认
_HEADER_MAP.update({field: field for field in Translator.EDITABLE})
_HEADER_MAP.update({
    "id": "id",
    "ID": "id",
    "译员ID": "id",
    "译员id": "id",
})
_BOOL_FIELDS = {"nda_signed"}
_DATE_FIELDS = {
    "onboarding_date",
    "rate_confirmed_date",
    "contract_expiry",
    "last_contact",
}
_ENUM_ALIASES = {
    "gender": {
        "男": "male", "male": "male",
        "女": "female", "female": "female",
    },
    "entity_type": {
        "个人": "individual", "个人译员": "individual", "individual": "individual",
        "供应商": "vendor", "vendor": "vendor",
    },
}
_PROJECT_HEADER_MAP = {
    "translator_id": "translator_id", "译员ID": "translator_id",
    "translator_name": "translator_name", "译员姓名": "translator_name", "姓名": "translator_name",
    "translator_email": "translator_email", "译员邮箱": "translator_email", "邮箱": "translator_email",
    "cooperation_source": "cooperation_source", "合作来源": "cooperation_source",
    "project_status": "project_status", "项目状态": "project_status",
    "project_name": "project_name", "项目名称": "project_name",
    "external_company": "external_company", "合作公司": "external_company",
    "role": "role", "角色": "role",
    "source_lang": "source_lang", "源语言": "source_lang",
    "target_lang": "target_lang", "目标语言": "target_lang",
    "start_date": "start_date", "开始日期": "start_date",
    "end_date": "end_date", "结束日期": "end_date",
    "remaining_volume": "remaining_volume", "剩余量": "remaining_volume",
    "deadline": "deadline", "截止日期": "deadline",
    "remarks": "remarks", "备注": "remarks",
}
_PROJECT_ENUM_ALIASES = {
    "cooperation_source": {
        "我司合作": "our_company", "与我司合作": "our_company",
        "our_company": "our_company",
        "外部合作": "external", "与别家合作": "external", "external": "external",
    },
    "project_status": {
        "当前": "current", "当前项目": "current", "current": "current",
        "过往": "past", "过往项目": "past", "past": "past",
    },
}
_ALIAS_HEADER_MAP = {
    "translator_id": "translator_id",
    "译员ID": "translator_id",
    "译员id": "translator_id",
    "translator_name": "translator_name",
    "译员姓名": "translator_name",
    "姓名": "translator_name",
    "translator_email": "translator_email",
    "译员邮箱": "translator_email",
    "邮箱": "translator_email",
    "alias": "alias",
    "名称映射": "alias",
    "别名": "alias",
    "曾用名": "alias",
}
_PO_HEADER_MAP = {
    "translator_id": "translator_id", "译员ID": "translator_id", "译员id": "translator_id", "ID": "translator_id",
    "translator": "translator_name", "translator_name": "translator_name", "译员": "translator_name", "姓名": "translator_name",
    "settlement_month": "settlement_month", "结算月": "settlement_month", "月份": "settlement_month", "年月": "settlement_month",
    "project": "project", "项目": "project",
    "source_lang": "source_lang", "源语言": "source_lang", "源语": "source_lang",
    "target_lang": "target_lang", "目标语言": "target_lang", "目标语": "target_lang",
    "role": "role", "任务类型": "role", "类型": "role", "角色": "role",
    "word_count": "word_count", "字数": "word_count", "字数（字）": "word_count", "字符数": "word_count",
    "rate": "rate", "单价": "rate", "单价（/千字）": "rate", "费率": "rate",
    "currency": "currency", "币种": "currency",
    "status": "status", "状态": "status",
    "po_number": "po_number", "PO号": "po_number", "PO 号": "po_number", "po_number": "po_number",
    "remarks": "remarks", "备注": "remarks",
}

_PROJECTLIST_LANGUAGE_MAP = {
    "简体中文": "ZH-HANS",
    "中文": "ZH-HANS",
    "台湾繁体": "ZH-HANT",
    "繁体中文": "ZH-HANT",
    "香港繁体": "ZH-HK",
    "英语": "EN",
    "英文": "EN",
    "美式英语": "EN-US",
    "英式英语": "EN-GB",
    "日语": "JA",
    "韩语": "KO",
    "法语": "FR",
    "德语": "DE",
    "西班牙语": "ES",
    "西语": "ES",
    "拉美西语": "ES-LA",
    "葡萄牙语": "PT",
    "巴西葡语": "PT-BR",
    "意大利语": "IT",
    "俄语": "RU",
    "乌克兰语": "UK",
    "波兰语": "PL",
    "荷兰语": "NL",
    "土耳其语": "TR",
    "阿拉伯语": "AR",
    "泰语": "TH",
    "越南语": "VI",
    "印尼语": "ID",
    "印度尼西亚语": "ID",
    "马来语": "MS",
    "台繁": "ZH-HANT",
    "藏语": "BO",
    "土语": "TR",
}

_PROJECTLIST_GROUP_LANGUAGES = {"欧洲语言", "亚洲语言"}
_PROJECTLIST_PROJECT_LANGUAGE_HINTS = {
    "台繁": "ZH-HANT",
    "藏语": "BO",
    "西语": "ES",
    "土语": "TR",
    "法语": "FR",
    "德语": "DE",
    "俄语": "RU",
    "韩语": "KO",
    "日语": "JA",
    "泰语": "TH",
    "越南语": "VI",
    "印尼语": "ID",
    "马来语": "MS",
}


def _norm_header(c):
    return str(c).replace("（必填）", "").replace("*", "").strip() if c is not None else ""


def _norm_month_value(v):
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m")
    s = str(v).strip()
    return s[:7] if len(s) >= 7 else s


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _norm_projectlist_header(value):
    return re.sub(r"[\s（）()【】\[\]_/·:：]+", "", str(value or "")).casefold()


def _number(value):
    if _blank(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text_value = str(value).replace(",", "").strip()
    try:
        return float(text_value)
    except ValueError:
        return None


def _projectlist_language(value, project=None):
    if _blank(value):
        return None
    raw = re.split(r"[,，;/；、]", str(value).strip())[0].strip()
    if raw in _PROJECTLIST_GROUP_LANGUAGES:
        project_text = str(project or "")
        for hint, code in _PROJECTLIST_PROJECT_LANGUAGE_HINTS.items():
            if hint in project_text:
                return code
    return _PROJECTLIST_LANGUAGE_MAP.get(raw, raw.upper())


def _projectlist_role(value):
    raw = str(value or "").strip()
    upper = raw.upper()
    if "一口价" in raw:
        return "一口价"
    if "MTPE" in upper or "AIPE" in upper:
        return "MTPE"
    if "LQA" in upper:
        return "LQA"
    if "LQE" in upper:
        return "LQE"
    if "审校" in raw or "校对" in raw:
        return "审校"
    if "翻译" in raw:
        return "翻译"
    return "其他"


def _projectlist_checked(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = re.sub(r"\s+", "", str(value or "")).casefold()
    return normalized in {
        "✅", "☑", "☒", "√", "✔", "是", "true", "1", "已勾选", "已结算",
    }


def _projectlist_month(value, deadline, filename):
    month = None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m")
    match = re.search(r"(\d{1,2})\s*月", str(value or ""))
    if match:
        month = int(match.group(1))
    elif re.fullmatch(r"\d{4}-\d{1,2}", str(value or "").strip()):
        year, month_value = str(value).strip().split("-")
        return f"{int(year):04d}-{int(month_value):02d}"
    if not month or not 1 <= month <= 12:
        return None
    year = None
    if isinstance(deadline, (datetime, date)):
        year = deadline.year
    else:
        deadline_year = re.search(r"(20\d{2})", str(deadline or ""))
        if deadline_year:
            year = int(deadline_year.group(1))
    if not year:
        filename_year = re.search(r"(20\d{2})", filename or "")
        year = int(filename_year.group(1)) if filename_year else date.today().year
    return f"{year:04d}-{month:02d}"


def _find_projectlist_sheet_and_header(wb):
    target = next(
        (sheet for sheet in wb.worksheets if "projectlist" in sheet.title.casefold()),
        None,
    )
    if not target:
        return None, None, None
    required = {
        _norm_projectlist_header("项目名称（稿件/LQA批次）"),
        _norm_projectlist_header("目标语言"),
        _norm_projectlist_header("指定译员"),
        _norm_projectlist_header("工作类型"),
    }
    for row_no in range(1, min(target.max_row, 10) + 1):
        values = [cell.value for cell in target[row_no]]
        normalized = {_norm_projectlist_header(value) for value in values}
        if required.issubset(normalized):
            return target, row_no, values
    return target, None, None


def _projectlist_records(wb, filename, *, validate_financial=False):
    sheet, header_row, headers = _find_projectlist_sheet_and_header(wb)
    if not sheet:
        return None
    if not header_row:
        raise HTTPException(400, "Projectlist 工作表前 10 行未找到标准表头")
    index = {
        _norm_projectlist_header(value): column
        for column, value in enumerate(headers)
        if not _blank(value)
    }

    def column(*labels):
        for label in labels:
            key = _norm_projectlist_header(label)
            if key in index:
                return index[key]
        return None

    columns = {
        "project": column("项目名称（稿件/LQA批次）"),
        "deadline": column("DDL"),
        "target_lang": column("目标语言"),
        "fee_cny": column("稿费金额（CNY）"),
        "translator_name": column("指定译员"),
        "role": column("工作类型"),
        "rate": column("翻译费率"),
        "currency": column("币种"),
        "quantity": column("REPNEW 实际"),
        "quantity_wwc": column("译员WWC字数"),
        "quantity_fallback": column("REPNEW & 小时数"),
        "settlement_month": column("译员PO时间（X月）"),
        "settlement_po": column("结算PO", "结算 PO"),
        "source_lang": column("原语言"),
        "client": column("客户公司"),
    }

    def value(row, field):
        position = columns[field]
        return row[position] if position is not None and position < len(row) else None

    inferred_targets = defaultdict(set)
    for row_no in range(header_row + 1, sheet.max_row + 1):
        row = tuple(cell.value for cell in sheet[row_no])
        project = str(value(row, "project") or "").strip()
        translator_name = str(value(row, "translator_name") or "").strip()
        source_lang = _projectlist_language(value(row, "source_lang"), project)
        target_lang = _projectlist_language(value(row, "target_lang"), project)
        if translator_name and source_lang and target_lang in LANGUAGE_SET:
            inferred_targets[(translator_name, source_lang)].add(target_lang)

    records, invalid_rows = [], []
    source_checked_rows = 0
    source_unchecked_rows = 0
    occurrences = defaultdict(int)
    for row_no in range(header_row + 1, sheet.max_row + 1):
        row = tuple(cell.value for cell in sheet[row_no])
        raw_settlement_po = value(row, "settlement_po")
        if not _blank(raw_settlement_po):
            if _projectlist_checked(raw_settlement_po):
                source_checked_rows += 1
            else:
                source_unchecked_rows += 1
        project = str(value(row, "project") or "").strip()
        translator_name = str(value(row, "translator_name") or "").strip()
        raw_role = str(value(row, "role") or "").strip()
        if not any((project, translator_name, raw_role)):
            continue
        deadline = value(row, "deadline")
        settlement_po_checked = _projectlist_checked(
            value(row, "settlement_po")
        )
        settlement_month = _projectlist_month(
            value(row, "settlement_month"), deadline, filename,
        )
        if not translator_name:
            invalid_rows.append({
                "sheet": sheet.title,
                "row": row_no,
                "error": "缺指定译员",
                "settlement_po_checked": settlement_po_checked,
            })
            continue
        if not project:
            invalid_rows.append({
                "sheet": sheet.title,
                "row": row_no,
                "error": "缺项目名称",
                "settlement_po_checked": settlement_po_checked,
            })
            continue
        if validate_financial and not settlement_po_checked and not settlement_month:
            invalid_rows.append({"sheet": sheet.title, "row": row_no, "error": "缺有效译员PO时间"})
            continue
        role = _projectlist_role(raw_role)
        rate = _number(value(row, "rate"))
        quantity = _number(value(row, "quantity"))
        if quantity is None:
            quantity = _number(value(row, "quantity_wwc"))
        if quantity is None:
            quantity = _number(value(row, "quantity_fallback"))
        currency = str(value(row, "currency") or "CNY").strip().upper()
        fee_cny = _number(value(row, "fee_cny"))
        pricing_mode = "per_1000"
        amount = None
        if role in {"LQA", "LQE"}:
            pricing_mode = "per_hour"
        elif role == "一口价":
            pricing_mode = "fixed"
            if currency == "CNY" and fee_cny is not None and fee_cny > 0:
                amount = fee_cny
            elif rate is not None and quantity is not None:
                amount = rate * quantity
            else:
                amount = rate
        elif rate is not None and 0 < rate < 10:
            rate *= 1000
        if (
            validate_financial
            and not settlement_po_checked
            and quantity is None
            and pricing_mode not in {"fixed", "manual"}
        ):
            invalid_rows.append({"sheet": sheet.title, "row": row_no, "error": "缺有效字数或小时数"})
            continue
        if (
            validate_financial
            and not settlement_po_checked
            and pricing_mode == "fixed"
            and amount is None
        ):
            invalid_rows.append({"sheet": sheet.title, "row": row_no, "error": "一口价缺固定金额"})
            continue
        if (
            validate_financial
            and not settlement_po_checked
            and pricing_mode != "fixed"
            and rate is None
        ):
            invalid_rows.append({"sheet": sheet.title, "row": row_no, "error": "缺有效翻译费率"})
            continue
        source_lang = _projectlist_language(value(row, "source_lang"), project)
        target_lang = _projectlist_language(value(row, "target_lang"), project)
        if target_lang not in LANGUAGE_SET:
            candidates = inferred_targets.get((translator_name, source_lang), set())
            if len(candidates) == 1:
                target_lang = next(iter(candidates))
        fingerprint_fields = {
            "project": project,
            "translator_name": translator_name,
            "settlement_po_checked": settlement_po_checked,
            "settlement_month": settlement_month,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "role": role,
            "quantity": quantity,
            "rate": rate,
            "amount": amount,
            "currency": currency,
        }
        base = json.dumps(
            fingerprint_fields, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        )
        occurrences[base] += 1
        source_key = hashlib.sha256(
            f"projectlist|{base}|{occurrences[base]}".encode()
        ).hexdigest()
        client = str(value(row, "client") or "").strip()
        records.append({
            "translator_name": translator_name,
            "settlement_po_checked": settlement_po_checked,
            "settlement_month": settlement_month,
            "project": project,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "role": role,
            "word_count": quantity,
            "rate": rate,
            "amount": amount,
            "pricing_mode": pricing_mode,
            "currency": currency,
            "status": "未开票",
            "source_key": source_key,
            "source_name": f"{Path(filename or 'Projectlist.xlsx').name}#{sheet.title}"[:255],
            "source_row": row_no,
            "remarks": f"Projectlist 导入；原工作类型：{raw_role}"
            + (f"；客户：{client}" if client else ""),
        })
    return {
        "sheet": sheet.title,
        "header_row": header_row,
        "records": records,
        "invalid_rows": invalid_rows,
        "source_checked_rows": source_checked_rows,
        "source_unchecked_rows": source_unchecked_rows,
    }


def _project_translator_id(
    session: Session,
    translators,
    raw_id,
    raw_email,
    raw_name,
):
    if not _blank(raw_id):
        try:
            tid = int(raw_id)
        except (TypeError, ValueError):
            raise ValueError("译员ID不是整数") from None
        if any(t.id == tid for t in translators):
            return tid
        raise ValueError("译员ID不存在")
    if not _blank(raw_email):
        email = str(raw_email).strip()
        matched = [t for t in translators if t.email == email]
        if len(matched) == 1:
            return matched[0].id
        if len(matched) > 1:
            raise ValueError("译员邮箱匹配不唯一")
    if not _blank(raw_name):
        return _find_translator_id(session, None, raw_name)
    raise ValueError("译员不存在")


def _find_translator_id(s: Session, raw_id, raw_name):
    if not _blank(raw_id):
        try:
            tid = int(raw_id)
        except (TypeError, ValueError):
            raise ValueError("译员ID不是整数") from None
        t = s.get(Translator, tid)
        if not t or t.deleted_at:
            raise ValueError("译员ID不存在")
        return tid
    if _blank(raw_name):
        raise ValueError("缺译员")
    name = str(raw_name).strip()
    matches = exact_translator_ids_for_name(s, name)
    if not matches:
        matches = fuzzy_translator_ids_for_name(s, name)
    if not matches:
        raise ValueError("译员不存在")
    if len(matches) > 1:
        raise ValueError("译员匹配不唯一")
    return next(iter(matches))


# ---------------- 审计 ----------------
@router.get("/audit")
def list_audit(who: str = Depends(require_editor)):
    with Session(engine) as s:
        rows = s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100)).all()
        return [r.as_dict() for r in rows]


# ---------------- 导入导出 ----------------
@router.get("/export/translators")
def export_translators():
    from openpyxl import Workbook
    with Session(engine) as s:
        rows = s.scalars(select(Translator).where(Translator.deleted_at.is_(None)).order_by(Translator.id)).all()
        wb = Workbook()
        ws = wb.active
        ws.title = "译员"
        ws.append(TR_COLS)
        for t in rows:
            d = t.as_dict()
            ws.append([d.get(c) for c in TR_COLS])
        project_ws = wb.create_sheet("项目经历")
        project_ws.append(PROJECT_EXPORT_COLS)
        translator_map = {t.id: t for t in rows}
        projects = s.scalars(
            select(TranslatorProjectExperience)
            .where(TranslatorProjectExperience.translator_id.in_(list(translator_map)))
            .order_by(TranslatorProjectExperience.translator_id, TranslatorProjectExperience.id)
        ).all() if translator_map else []
        for project in projects:
            translator = translator_map[project.translator_id]
            data = project.as_dict() | {
                "translator_name": translator.name,
                "translator_email": translator.email,
            }
            project_ws.append([data.get(column) for column in PROJECT_EXPORT_COLS])
        alias_ws = wb.create_sheet("名称映射")
        alias_ws.append(ALIAS_EXPORT_COLS)
        aliases = s.scalars(
            select(TranslatorAlias)
            .where(TranslatorAlias.translator_id.in_(list(translator_map)))
            .order_by(TranslatorAlias.translator_id, TranslatorAlias.id)
        ).all() if translator_map else []
        for alias in aliases:
            translator = translator_map[alias.translator_id]
            data = alias.as_dict() | {
                "translator_name": translator.name,
                "translator_email": translator.email,
            }
            alias_ws.append([data.get(column) for column in ALIAS_EXPORT_COLS])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=translators.xlsx"})


@router.post("/import/translators")
def import_translators(file: UploadFile, who: str = Depends(require_editor)):
    """无 ID 时新增；同一稳定译员 ID 时覆盖主数据；派生字段不导入。"""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file.file.read()))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"imported": 0, "updated": 0}
    header = [_norm_header(c) for c in rows[0]]
    mapped_columns = [
        (position, field)
        for position, column in enumerate(header)
        if (field := _HEADER_MAP.get(column))
    ]
    n, updated, skipped, invalid_rows = 0, 0, 0, []
    imported_projects, skipped_projects, invalid_project_rows = 0, 0, []
    imported_aliases, skipped_aliases, invalid_alias_rows = 0, 0, []

    def convert_value(field, value):
        if _blank(value):
            return None
        if field in _BOOL_FIELDS:
            return str(value).strip() in ("是", "true", "True", "1", "Y", "y")
        if field in _DATE_FIELDS:
            return str(value)[:10]
        if field in _ENUM_ALIASES:
            return _ENUM_ALIASES[field].get(
                str(value).strip().lower(),
                value,
            )
        if field == "name":
            return str(value).strip()
        return value

    def parse_translator_id(value):
        if isinstance(value, bool):
            raise ValueError("译员ID不是整数")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError("译员ID不是整数") from None
        if not numeric.is_integer() or numeric <= 0:
            raise ValueError("译员ID不是正整数")
        return int(numeric)

    def validation_error(error):
        return "；".join(
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in error.errors(include_url=False)
        )

    def add_pairs(session, translator_id, pairs_value):
        if not pairs_value:
            return
        existing_pairs = {
            (pair.source_lang, pair.target_lang)
            for pair in session.scalars(
                select(LanguagePair).where(
                    LanguagePair.translator_id == translator_id
                )
            ).all()
        }
        for pair_text in str(pairs_value).split(","):
            pair_text = pair_text.strip()
            separator = "→" if "→" in pair_text else (
                "->" if "->" in pair_text else None
            )
            if not separator:
                continue
            source_lang, target_lang = pair_text.split(separator, 1)
            key = (source_lang.strip(), target_lang.strip())
            if all(key) and key not in existing_pairs:
                session.add(LanguagePair(
                    translator_id=translator_id,
                    source_lang=key[0],
                    target_lang=key[1],
                ))
                existing_pairs.add(key)

    with Session(engine) as s:
        seen_ids = set()
        for row_no, r in enumerate(rows[1:], start=2):
            if not any(not _blank(value) for value in r):
                continue
            data = {}
            raw_id = None
            for position, field in mapped_columns:
                value = r[position] if position < len(r) else None
                if field == "id":
                    raw_id = value
                else:
                    data[field] = convert_value(field, value)
            try:
                translator_id = None
                if not _blank(raw_id):
                    translator_id = parse_translator_id(raw_id)
                    if translator_id in seen_ids:
                        raise ValueError("同一文件译员ID重复")
                    seen_ids.add(translator_id)
                if translator_id is not None:
                    translator = s.get(Translator, translator_id)
                    if not translator or translator.deleted_at:
                        raise ValueError("译员ID不存在")
                    merged = {
                        field: getattr(translator, field, None)
                        for field in TranslatorIn.model_fields
                        if hasattr(translator, field)
                    }
                    merged.update(data)
                    if not merged.get("name"):
                        raise ValueError("姓名不能为空")
                    clean = TranslatorIn(**merged).model_dump()
                    clean.pop("internal_rating", None)
                    email = clean.get("email")
                    if email and s.scalar(
                        select(Translator).where(
                            Translator.email == email,
                            Translator.id != translator_id,
                            Translator.deleted_at.is_(None),
                        )
                    ):
                        raise ValueError("邮箱已属于其他译员")
                    assert_name_not_reserved(s, clean["name"], translator_id)
                    old_name = translator.name
                    with s.begin_nested():
                        for field, value in clean.items():
                            setattr(translator, field, value)
                        if (
                            normalize_translator_name(old_name)
                            != normalize_translator_name(translator.name)
                        ):
                            add_translator_alias(s, translator_id, old_name)
                        if "language_pairs" in data:
                            add_pairs(
                                s,
                                translator_id,
                                clean.get("language_pairs"),
                            )
                        resync_translator(s, translator_id)
                        audit(
                            s,
                            who,
                            "Excel同ID覆盖",
                            "译员",
                            translator_id,
                            translator.name,
                        )
                    updated += 1
                    continue
                create_data = {
                    field: value
                    for field, value in data.items()
                    if value is not None
                }
                create_data.setdefault("status", "Active")
                if not create_data.get("name"):
                    raise ValueError("姓名不能为空")
                clean = TranslatorIn(**create_data).model_dump()
                clean.pop("internal_rating", None)
                email = clean.get("email")
                if email and s.scalar(
                    select(Translator).where(
                        Translator.email == email,
                        Translator.deleted_at.is_(None),
                    )
                ):
                    skipped += 1
                    continue
                assert_name_not_reserved(s, clean["name"])
                with s.begin_nested():
                    translator = Translator(**clean)
                    s.add(translator)
                    s.flush()
                    add_pairs(s, translator.id, clean.get("language_pairs"))
                    resync_translator(s, translator.id)
                n += 1
            except ValidationError as error:
                invalid_rows.append({
                    "row": row_no,
                    "error": validation_error(error),
                })
            except (ValueError, HTTPException) as error:
                invalid_rows.append({
                    "row": row_no,
                    "error": str(getattr(error, "detail", error)),
                })
        s.flush()

        translators = s.scalars(
            select(Translator).where(Translator.deleted_at.is_(None))
        ).all()
        alias_ws = wb["名称映射"] if "名称映射" in wb.sheetnames else None
        if alias_ws:
            alias_rows = list(alias_ws.iter_rows(values_only=True))
            if alias_rows:
                alias_header = [_norm_header(c) for c in alias_rows[0]]
                for row_no, row in enumerate(alias_rows[1:], start=2):
                    raw = {}
                    for column, value in zip(alias_header, row):
                        field = _ALIAS_HEADER_MAP.get(column)
                        if field and not _blank(value):
                            raw[field] = value
                    if not raw:
                        continue
                    try:
                        translator_id = _project_translator_id(
                            s,
                            translators,
                            raw.get("translator_id"),
                            raw.get("translator_email"),
                            raw.get("translator_name"),
                        )
                        if _blank(raw.get("alias")):
                            raise ValueError("缺名称映射")
                        with s.begin_nested():
                            _, created = add_translator_alias(
                                s,
                                translator_id,
                                str(raw["alias"]),
                            )
                        if created:
                            imported_aliases += 1
                        else:
                            skipped_aliases += 1
                    except (ValueError, HTTPException) as error:
                        invalid_alias_rows.append({
                            "row": row_no,
                            "error": str(getattr(error, "detail", error)),
                        })

        project_ws = wb["项目经历"] if "项目经历" in wb.sheetnames else None
        if project_ws:
            project_rows = list(project_ws.iter_rows(values_only=True))
            if project_rows:
                project_header = [_norm_header(c) for c in project_rows[0]]
                translators = s.scalars(
                    select(Translator).where(Translator.deleted_at.is_(None))
                ).all()
                existing_projects = {
                    (
                        project.translator_id,
                        project.project_status,
                        project.project_name,
                        project.cooperation_source,
                        project.external_company or "",
                    )
                    for project in s.scalars(select(TranslatorProjectExperience)).all()
                }
                for row_no, row in enumerate(project_rows[1:], start=2):
                    raw = {}
                    for column, value in zip(project_header, row):
                        field = _PROJECT_HEADER_MAP.get(column)
                        if not field or _blank(value):
                            continue
                        if field in {"start_date", "end_date", "deadline"}:
                            value = str(value)[:10]
                        elif field in _PROJECT_ENUM_ALIASES:
                            value = _PROJECT_ENUM_ALIASES[field].get(
                                str(value).strip().lower(), value,
                            )
                        raw[field] = value
                    if not raw:
                        continue
                    try:
                        translator_id = _project_translator_id(
                            s,
                            translators,
                            raw.pop("translator_id", None),
                            raw.pop("translator_email", None),
                            raw.pop("translator_name", None),
                        )
                        clean = ProjectExperienceIn(**raw).model_dump()
                        duplicate_key = (
                            translator_id,
                            clean["project_status"],
                            clean["project_name"],
                            clean["cooperation_source"],
                            clean.get("external_company") or "",
                        )
                        if duplicate_key in existing_projects:
                            skipped_projects += 1
                            continue
                        svc_add_project_experience(
                            s, translator_id, clean, who,
                        )
                        existing_projects.add(duplicate_key)
                        imported_projects += 1
                    except ValidationError as error:
                        invalid_project_rows.append({
                            "row": row_no,
                            "error": "；".join(
                                f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                                for item in error.errors(include_url=False)
                            ),
                        })
                    except (ValueError, HTTPException) as error:
                        invalid_project_rows.append({
                            "row": row_no,
                            "error": str(getattr(error, "detail", error)),
                        })
        audit(
            s, who, "导入", "译员", None,
            f"译员新增{n}条、同ID覆盖{updated}条"
            f"(重复邮箱{skipped}，错误{len(invalid_rows)})；"
            f"名称映射{imported_aliases}条"
            f"(重复{skipped_aliases}，错误{len(invalid_alias_rows)})；"
            f"项目经历{imported_projects}条"
            f"(重复{skipped_projects}，错误{len(invalid_project_rows)})",
        )
        s.commit()
    return {
        "imported": n,
        "updated": updated,
        "skipped_dup_email": skipped,
        "invalid_rows": invalid_rows,
        "imported_aliases": imported_aliases,
        "skipped_dup_aliases": skipped_aliases,
        "invalid_alias_rows": invalid_alias_rows,
        "imported_projects": imported_projects,
        "skipped_dup_projects": skipped_projects,
        "invalid_project_rows": invalid_project_rows,
    }


@router.post("/import/po")
def import_po(
    file: UploadFile,
    preview: bool = False,
    projectlist_po_state: str = "all",
    who: str = Depends(require_editor),
):
    """预览或导入标准 PO 表及原始 Projectlist。"""
    from openpyxl import load_workbook

    payload = file.file.read()
    try:
        wb = load_workbook(io.BytesIO(payload), data_only=True)
    except Exception as error:
        raise HTTPException(400, f"Excel 无法读取：{error}") from error
    filename = file.filename or "po.xlsx"
    file_hash = hashlib.sha256(payload).hexdigest()
    if projectlist_po_state not in {"all", "checked", "unchecked"}:
        raise HTTPException(400, "Projectlist 结算PO筛选值非法")
    projectlist = _projectlist_records(
        wb,
        filename,
        validate_financial=False,
    )
    if projectlist and not preview:
        raise HTTPException(
            409,
            "Projectlist 的 PO 数量规则仍待 PM 确认；仅允许只读预览，不写入 PO",
        )
    preview_rows = []
    imported = 0
    skipped_dup_po = 0
    invalid_rows = list(projectlist["invalid_rows"]) if projectlist else []

    def error_message(error):
        if isinstance(error, ValidationError):
            return "；".join(
                f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                for item in error.errors(include_url=False)
            )
        if isinstance(error, HTTPException):
            return str(error.detail)
        return str(error)

    with Session(engine) as s:
        existing_po = {
            value for (value,) in s.execute(select(PO.po_number)).all() if value
        }
        if projectlist:
            checked_rows = projectlist["source_checked_rows"]
            unchecked_rows = projectlist["source_unchecked_rows"]

            def selected(checked):
                return (
                    projectlist_po_state == "all"
                    or (
                        projectlist_po_state == "checked"
                        and checked
                    )
                    or (
                        projectlist_po_state == "unchecked"
                        and not checked
                    )
                )

            selected_records = [
                record
                for record in projectlist["records"]
                if selected(record["settlement_po_checked"])
            ]
            invalid_rows = [
                row
                for row in invalid_rows
                if selected(bool(row.get("settlement_po_checked")))
            ]
            selected_rows = len(selected_records) + len(invalid_rows)
            ignored_rows = max(
                0,
                checked_rows + unchecked_rows
                - len(projectlist["records"])
                - len(projectlist["invalid_rows"]),
            )
            matched_rows = 0
            mapping_ready = 0
            skipped_settled = 0
            for record in selected_records:
                row_no = record["source_row"]
                try:
                    translator_id = _find_translator_id(
                        s, None, record["translator_name"],
                    )
                    matched_rows += 1
                    if record["settlement_po_checked"]:
                        action = "skip_settled"
                        skipped_settled += 1
                    else:
                        action = "blocked_quantity_rule"
                        mapping_ready += 1
                    preview_rows.append({
                        "translator_id": translator_id,
                        "translator_name": record["translator_name"],
                        "project": record["project"],
                        "settlement_month": record["settlement_month"],
                        "source_lang": record["source_lang"],
                        "target_lang": record["target_lang"],
                        "role": record["role"],
                        "currency": record["currency"],
                        "source_row": row_no,
                        "settlement_po_checked": (
                            record["settlement_po_checked"]
                        ),
                        "action": action,
                    })
                except (ValidationError, ValueError, HTTPException) as error:
                    invalid_rows.append({
                        "sheet": projectlist["sheet"],
                        "row": row_no,
                        "error": error_message(error),
                        "settlement_po_checked": (
                            record["settlement_po_checked"]
                        ),
                    })
            return {
                "preview": True,
                "source_format": "projectlist",
                "sheet": projectlist["sheet"],
                "header_row": projectlist["header_row"],
                "file_hash": file_hash,
                "projectlist_po_state": projectlist_po_state,
                "write_enabled": False,
                "quantity_rule_confirmed": False,
                "ready": 0,
                "mapping_ready": mapping_ready,
                "matched_rows": matched_rows,
                "checked_rows": checked_rows,
                "unchecked_rows": unchecked_rows,
                "selected_rows": selected_rows,
                "ignored_rows": ignored_rows,
                "skipped_settled": skipped_settled,
                "imported": 0,
                "skipped_dup_po": 0,
                "invalid_rows": invalid_rows,
                "preview_rows": preview_rows[:100],
                "preview_truncated": len(preview_rows) > 100,
            }

        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {
                "preview": preview,
                "source_format": "standard",
                "imported": 0,
                "ready": 0,
                "skipped_dup_po": 0,
                "invalid_rows": [],
                "preview_rows": [],
            }
        header = [_norm_header(cell) for cell in rows[0]]
        for row_no, row_values in enumerate(rows[1:], start=2):
            raw = {}
            for column_name, value in zip(header, row_values):
                field = _PO_HEADER_MAP.get(column_name)
                if not field or _blank(value):
                    continue
                if field == "settlement_month":
                    value = _norm_month_value(value)
                raw[field] = value
            if not raw:
                continue
            try:
                data = {
                    key: value
                    for key, value in raw.items()
                    if key != "translator_name"
                }
                data["translator_id"] = _find_translator_id(
                    s, raw.get("translator_id"), raw.get("translator_name"),
                )
                if data.get("po_number"):
                    data["po_number"] = str(data["po_number"]).strip()
                    if data["po_number"] in existing_po:
                        skipped_dup_po += 1
                        continue
                clean = POIn(**data).model_dump()
                prepared = prepare_po(s, clean, check_duplicate=False)
                if preview:
                    preview_rows.append({
                        **prepared,
                        "translator_name": raw.get("translator_name"),
                        "expected_amount": expected_amount(
                            prepared.get("word_count"),
                            prepared.get("rate"),
                            prepared.get("pricing_mode"),
                            prepared.get("amount"),
                        ),
                        "action": "import",
                    })
                else:
                    po_row = svc_create_po(s, prepared, who)
                    if po_row.po_number:
                        existing_po.add(po_row.po_number)
                    imported += 1
            except (ValidationError, ValueError, HTTPException) as error:
                invalid_rows.append({
                    "sheet": ws.title,
                    "row": row_no,
                    "error": error_message(error),
                })
        if not preview:
            audit(
                s, who, "导入", "PO", None,
                f"{imported} 条(重复{skipped_dup_po}，错误{len(invalid_rows)})",
            )
            s.commit()
    return {
        "preview": preview,
        "source_format": "standard",
        "sheet": wb.active.title,
        "header_row": 1,
        "file_hash": file_hash,
        "ready": len(preview_rows) if preview else imported,
        "imported": imported,
        "skipped_dup_po": skipped_dup_po,
        "invalid_rows": invalid_rows,
        "preview_rows": preview_rows[:100],
        "preview_truncated": len(preview_rows) > 100,
    }


@router.post("/import/lqe")
def import_lqe(file: UploadFile, period: Optional[str] = None, who: str = Depends(require_editor)):
    """读 LQE 流程产出的 <label>_LQE报告.xlsx 的「汇总」sheet，按子表名匹配译员，写入质量记分卡。"""
    import re

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(file.file.read()), data_only=True)
    data_rows, project = None, None
    for ws in wb.worksheets:
        allr = list(ws.iter_rows(values_only=True))
        for r in allr[:4]:
            for c in r:
                if isinstance(c, str) and "项目" in c:
                    mp = re.search(r"项目\s*([^\s]+)", c)
                    if mp:
                        project = mp.group(1)
        for idx, r in enumerate(allr):
            if r and str(r[0]).strip() == "子表":
                data_rows = allr[idx + 1:]
                break
        if data_rows:
            break
    if data_rows is None:
        raise HTTPException(400, "未找到 LQE 汇总表（缺『子表/SCORE』表头）")
    period = period or date.today().strftime("%Y-%m")
    imported, unmatched, affected = 0, [], set()
    with Session(engine) as s:
        trs = s.scalars(select(Translator).where(Translator.deleted_at.is_(None))).all()
        for r in data_rows:
            name = str(r[0]).strip() if r and r[0] is not None else ""
            if not name or name == "合计":
                continue
            t = next((x for x in trs if x.name and (x.name in name or name in x.name)), None)
            if not t:
                unmatched.append(name)
                continue
            g = lambda i: (r[i] if i < len(r) else None)
            errs = int(g(3) or 0)
            crit = int(g(4) or 0)
            status_text = str(g(6) or "").strip()
            normalized_status = status_text.casefold()
            is_qualified = None
            if normalized_status:
                is_qualified = not any(
                    marker in normalized_status
                    for marker in ("fail", "不合格", "未通过")
                )
            s.add(QualityScore(translator_id=t.id, evaluation_period=period, project=project,
                               qa_type="LQE", score=g(5), critical_errors=crit,
                               minor_errors=max(0, errs - crit),
                               is_qualified=is_qualified,
                               failure_reason=status_text if is_qualified is False else None,
                               reviewer="LQE自动", feedback_notes=f"LQE导入 段数{g(1)} 词数{g(2)} STATUS{g(6)}"))
            affected.add(t.id)
            imported += 1
        for tid in affected:
            resync_translator(s, tid)
        audit(s, who, "导入", "LQE质量分", None, f"{imported}条 未匹配{len(unmatched)}")
        s.commit()
    return {"imported": imported, "unmatched": unmatched, "project": project, "period": period}
