"""审计日志、导入导出接口。"""
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import AuditLog, QualityScore, Translator
from ..security import require_editor
from ..services import audit, resync_translator

router = APIRouter(prefix="/api")

TR_COLS = ["id"] + list(Translator.EDITABLE) + list(Translator.DERIVED)   # 全 52 列


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
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(file.file.read()))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"imported": 0}
    header = [str(c) if c is not None else "" for c in rows[0]]
    n = 0
    with Session(engine) as s:
        existing = {e for (e,) in s.execute(select(Translator.email).where(Translator.deleted_at.is_(None))).all() if e}
        for r in rows[1:]:
            rec = dict(zip(header, r))
            name = rec.get("name")
            if not name:
                continue
            email = rec.get("email")
            if email and email in existing:
                continue
            s.add(Translator(name=str(name), email=email, wechat=rec.get("wechat"),
                             language_pairs=rec.get("language_pairs"),
                             translation_rate=rec.get("translation_rate"),
                             status=rec.get("status") or "Active",
                             internal_rating=rec.get("internal_rating"),
                             current_project=rec.get("current_project"),
                             contract_expiry=str(rec["contract_expiry"]) if rec.get("contract_expiry") else None,
                             remarks=rec.get("remarks")))
            if email:
                existing.add(email)
            n += 1
        audit(s, who, "导入", "译员", None, f"{n} 条")
        s.commit()
    return {"imported": n}


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
