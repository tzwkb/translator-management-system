"""审计日志、导入导出接口。"""
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import AuditLog, LanguagePair, QualityScore, Translator
from ..security import require_editor
from ..services import audit, resync_translator

router = APIRouter(prefix="/api")

TR_COLS = ["id"] + list(Translator.EDITABLE) + list(Translator.DERIVED)   # 全 52 列

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
    ("语言对", "language_pairs", False, None),
    ("翻译费率", "translation_rate", False, None),
    ("MTPE费率", "mtpe_rate", False, None),
    ("审校费率", "review_rate", False, None),
    ("LQA费率", "lqa_rate", False, None),
    ("报价确认日", "rate_confirmed_date", False, None),
    ("擅长领域", "domains", False, None),
    ("文本类型", "text_types", False, None),
    ("CAT工具", "cat_tools", False, None),
    ("内部评级", "internal_rating", False, ["S", "A", "B", "C", "D"]),
    ("试译结果", "trial_result", False, ["Pass", "Fail", "Pending"]),
    ("当前项目", "current_project", False, None),
    ("角色", "role", False, ["翻译", "审校", "MTPE", "LQA"]),
    ("日产字数", "daily_output", False, None),
    ("是否双休", "weekend_off", False, ["是", "否"]),
    ("档期", "availability", False, ["空闲", "部分空闲", "满负荷"]),
    ("结算币种", "currency", False, ["CNY", "USD", "EUR"]),
    ("支付方式", "payment_method", False, None),
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
_BOOL_FIELDS = {"weekend_off", "nda_signed"}
_DATE_FIELDS = {"onboarding_date", "rate_confirmed_date", "contract_expiry", "last_contact"}


def _norm_header(c):
    return str(c).replace("（必填）", "").replace("*", "").strip() if c is not None else ""


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
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=translators.xlsx"})


@router.post("/import/translators")
def import_translators(file: UploadFile, who: str = Depends(require_editor)):
    """按导入模板（中文表头，也认英文字段名）批量建档；邮箱重复跳过；派生字段不导入。"""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(file.file.read()))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"imported": 0}
    header = [_norm_header(c) for c in rows[0]]
    n, skipped = 0, 0
    with Session(engine) as s:
        existing = {e for (e,) in s.execute(select(Translator.email).where(Translator.deleted_at.is_(None))).all() if e}
        for r in rows[1:]:
            data = {}
            for col, val in zip(header, r):
                f = _HEADER_MAP.get(col)
                if not f or val is None or val == "":
                    continue
                if f in _BOOL_FIELDS:
                    val = str(val).strip() in ("是", "true", "True", "1", "Y", "y")
                elif f in _DATE_FIELDS:
                    val = str(val)[:10]
                data[f] = val
            if not data.get("name"):
                continue
            email = data.get("email")
            if email and email in existing:
                skipped += 1
                continue
            data["name"] = str(data["name"])
            data.setdefault("status", "Active")
            t = Translator(**data)
            s.add(t)
            s.flush()
            # 语言对：把逗号分隔串拆成子表行
            lp_str = data.get("language_pairs")
            if lp_str:
                for pair in str(lp_str).split(","):
                    p = pair.strip()
                    if "→" in p:
                        src, tgt = p.split("→", 1)
                        s.add(LanguagePair(translator_id=t.id, source_lang=src.strip(), target_lang=tgt.strip()))
            if email:
                existing.add(email)
            n += 1
        audit(s, who, "导入", "译员", None, f"{n} 条(跳过重复{skipped})")
        s.commit()
    return {"imported": n, "skipped_dup_email": skipped}


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
            s.add(QualityScore(translator_id=t.id, evaluation_period=period, project=project,
                               qa_type="LQE", score=g(5), critical_errors=crit,
                               minor_errors=max(0, errs - crit),
                               reviewer="LQE自动", feedback_notes=f"LQE导入 段数{g(1)} 词数{g(2)} STATUS{g(6)}"))
            affected.add(t.id)
            imported += 1
        for tid in affected:
            resync_translator(s, tid)
        audit(s, who, "导入", "LQE质量分", None, f"{imported}条 未匹配{len(unmatched)}")
        s.commit()
    return {"imported": imported, "unmatched": unmatched, "project": project, "period": period}
