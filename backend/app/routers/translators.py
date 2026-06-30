"""译员主表及其子表（报价/质量/合同/客诉/产能/支付）接口。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import (Capacity, Complaint, Contract, LanguagePair, PaymentInfo,
                      QualityScore,
                      RateChange, Translator)
from ..schemas import (CapacityIn, ComplaintIn, ContractIn, PaymentIn, QualityIn,
                       RateChangeIn, TranslatorIn)
from ..security import enc, require_editor, require_writer
from ..services import audit, get_translator, make_pending, resync_translator, svc_add_rate_change

router = APIRouter(prefix="/api")


# ---------------- 译员 ----------------
@router.get("/translators")
def list_translators():
    with Session(engine) as s:
        rows = s.scalars(select(Translator).where(Translator.deleted_at.is_(None)).order_by(Translator.id)).all()
        tids = [r.id for r in rows]
        lp_map = {}
        if tids:
            lps = s.scalars(select(LanguagePair).where(LanguagePair.translator_id.in_(tids)).order_by(LanguagePair.id)).all()
            for lp in lps:
                lp_map.setdefault(lp.translator_id, []).append(f"{lp.source_lang}→{lp.target_lang}")
        result = []
        for r in rows:
            r._cached_lp = ", ".join(lp_map.get(r.id, []))
            result.append(r.as_dict())
        return result


@router.post("/translators")
def create_translator(body: TranslatorIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        if body.email and s.scalar(select(Translator).where(Translator.email == body.email, Translator.deleted_at.is_(None))):
            raise HTTPException(400, "邮箱已存在")
        t = Translator(**body.model_dump())
        s.add(t)
        s.flush()
        audit(s, who, "新增", "译员", t.id, t.name)
        s.commit()
        s.refresh(t)
        return t.as_dict()


@router.put("/translators/{tid}")
def update_translator(tid: int, body: TranslatorIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        t = get_translator(s, tid)
        if body.email and s.scalar(select(Translator).where(Translator.email == body.email, Translator.id != tid, Translator.deleted_at.is_(None))):
            raise HTTPException(400, "邮箱已存在")
        for k, v in body.model_dump().items():
            setattr(t, k, v)
        audit(s, who, "编辑", "译员", tid, t.name)
        s.commit()
        s.refresh(t)
        return t.as_dict()


@router.delete("/translators/{tid}")
def delete_translator(tid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        t = get_translator(s, tid)
        t.deleted_at = datetime.now()
        audit(s, who, "删除", "译员", tid, t.name)
        s.commit()
        return {"ok": True}


# ---------------- 报价变更 ----------------
@router.get("/translators/{tid}/rate-changes")
def list_rate_changes(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(RateChange).where(RateChange.translator_id == tid)
                         .order_by(RateChange.change_date.desc(), RateChange.id.desc())).all()
        return [r.as_dict() for r in rows]


@router.post("/translators/{tid}/rate-changes")
def add_rate_change(tid: int, body: RateChangeIn, w=Depends(require_writer)):
    role, name = w
    with Session(engine) as s:
        get_translator(s, tid)
        d = body.model_dump()
        if role == "agent":
            return make_pending(s, name, "rate_change", tid, d)
        svc_add_rate_change(s, tid, d, name)
        s.commit()
        return {"ok": True}


# ---------------- 质量记分卡 ----------------
@router.get("/translators/{tid}/quality")
def list_quality(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(QualityScore).where(QualityScore.translator_id == tid)
                         .order_by(QualityScore.evaluation_period.desc(), QualityScore.id.desc())).all()
        return [r.as_dict() for r in rows]


@router.post("/translators/{tid}/quality")
def add_quality(tid: int, body: QualityIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        s.add(QualityScore(translator_id=tid, **body.model_dump()))
        audit(s, who, "新增", "质量记分", tid, f"{body.evaluation_period} {body.score}")
        resync_translator(s, tid)
        s.commit()
        return {"ok": True}


# ---------------- 合同 ----------------
@router.get("/translators/{tid}/contracts")
def list_contracts(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(Contract).where(Contract.translator_id == tid).order_by(Contract.id)).all()
        return [r.as_dict() for r in rows]


@router.post("/translators/{tid}/contracts")
def add_contract(tid: int, body: ContractIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        if body.contract_number and s.scalar(select(Contract).where(Contract.contract_number == body.contract_number)):
            raise HTTPException(400, "合同编号已存在")
        s.add(Contract(translator_id=tid, **body.model_dump()))
        audit(s, who, "新增", "合同", tid, body.contract_number or "")
        s.commit()
        return {"ok": True}


# ---------------- 语言对 ----------------
@router.get("/translators/{tid}/language-pairs")
def list_language_pairs(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(LanguagePair).where(LanguagePair.translator_id == tid).order_by(LanguagePair.id)).all()
        return [r.as_dict() for r in rows]


@router.post("/translators/{tid}/language-pairs")
def add_language_pair(tid: int, body: dict, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        lp = LanguagePair(translator_id=tid, source_lang=body.get("source_lang",""), target_lang=body.get("target_lang",""))
        s.add(lp)
        audit(s, who, "新增", "语言对", tid, f"{lp.source_lang}→{lp.target_lang}")
        resync_translator(s, tid)
        s.commit()
        s.refresh(lp)
        return lp.as_dict()


@router.delete("/translators/{tid}/language-pairs/{lpid}")
def delete_language_pair(tid: int, lpid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        lp = s.get(LanguagePair, lpid)
        if not lp or lp.translator_id != tid:
            raise HTTPException(404, "该语言对不存在")
        s.delete(lp)
        audit(s, who, "删除", "语言对", tid, f"{lp.source_lang}→{lp.target_lang}")
        resync_translator(s, tid)
        s.commit()
        return {"ok": True}


# ---------------- 客诉 ----------------
@router.get("/translators/{tid}/complaints")
def list_complaints(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(Complaint).where(Complaint.translator_id == tid)
                         .order_by(Complaint.date.desc(), Complaint.id.desc())).all()
        return [r.as_dict() for r in rows]


@router.post("/translators/{tid}/complaints")
def add_complaint(tid: int, body: ComplaintIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        s.add(Complaint(translator_id=tid, **body.model_dump()))
        audit(s, who, "新增", "客诉", tid, f"{body.complaint_type} {body.severity}")
        resync_translator(s, tid)
        s.commit()
        return {"ok": True}


# ---------------- 产能（占用 + 可用率；利用率字段已删 0629）----------------
@router.get("/translators/{tid}/capacity")
def list_capacity(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(Capacity).where(Capacity.translator_id == tid)
                         .order_by(Capacity.period_year, Capacity.period_month, Capacity.week_no)).all()
        by_week = {}
        for r in rows:
            by_week.setdefault((r.period_year, r.period_month, r.week_no), 0)
            by_week[(r.period_year, r.period_month, r.week_no)] += r.occupancy_pct
        weeks = [{"period": f"{y}-{mo:02d} W{w}", "occupancy": occ, "available": 100 - occ}
                 for (y, mo, w), occ in sorted(by_week.items())]
        return {"rows": [r.as_dict() for r in rows], "weeks": weeks}


@router.post("/translators/{tid}/capacity")
def add_capacity(tid: int, body: CapacityIn, w=Depends(require_writer)):
    role, name = w
    with Session(engine) as s:
        get_translator(s, tid)
        s.add(Capacity(translator_id=tid, **body.model_dump()))
        audit(s, name, "新增", "产能", tid, f"{body.period_year}-{body.period_month} W{body.week_no} {body.occupancy_pct}%")
        s.commit()
        return {"ok": True}


# ---------------- 支付信息（加密 + 脱敏）----------------
@router.get("/translators/{tid}/payment")
def get_payment(tid: int):
    with Session(engine) as s:
        p = s.get(PaymentInfo, tid)
        return p.as_dict() if p else None


@router.get("/translators/{tid}/payment/reveal")
def reveal_payment(tid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        p = s.get(PaymentInfo, tid)
        if not p:
            raise HTTPException(404, "无支付信息")
        audit(s, who, "查看明文", "支付信息", tid, "")
        s.commit()
        return p.as_dict(reveal=True)


@router.put("/translators/{tid}/payment")
def put_payment(tid: int, body: PaymentIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        p = s.get(PaymentInfo, tid) or PaymentInfo(translator_id=tid)
        p.currency = body.currency
        p.bank_name = body.bank_name
        p.payee_name = body.payee_name
        p.supports_wechat = body.supports_wechat
        p.remarks = body.remarks
        if body.bank_account:
            p.bank_account_enc = enc(body.bank_account)
        if body.id_card:
            p.id_card_enc = enc(body.id_card)
        s.add(p)
        audit(s, who, "保存", "支付信息", tid, "")
        s.commit()
        return p.as_dict()
