"""PO 结算与待审队列接口。"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import engine
from ..models import PO, PendingChange
from ..schemas import POIn, StatusIn
from ..security import require_editor, require_writer
from ..services import (PO_STATUSES, audit, expected_amount,
                        find_idempotent_request, make_pending, names_of,
                        needs_legacy_replay_validation, pending_request_hash,
                        prepare_po, prepare_po_status, svc_add_rate_change,
                        svc_create_po, svc_set_po_status)

router = APIRouter(prefix="/api")


# ---------------- PO ----------------
@router.get("/po")
def list_po(month: Optional[str] = None, status: Optional[str] = None):
    with Session(engine) as s:
        q = select(PO)
        if month:
            q = q.where(PO.settlement_month == month)
        if status:
            q = q.where(PO.status == status)
        rows = s.scalars(q.order_by(PO.settlement_month.desc(), PO.id)).all()
        nm = names_of(s, {r.translator_id for r in rows})
        out = []
        for r in rows:
            d = r.as_dict()
            d["translator_name"] = nm.get(r.translator_id, "?")
            exp = expected_amount(r.word_count, r.rate)
            d["expected_amount"] = exp
            d["amount_ok"] = abs(float(r.amount or 0) - exp) <= 0.02
            out.append(d)
        return out


@router.get("/po/summary")
def po_summary(month: str):
    with Session(engine) as s:
        rows = s.scalars(select(PO).where(PO.settlement_month == month)).all()
        cur = {}
        for r in rows:
            c = cur.setdefault(r.currency or "?", {"unpaid": 0.0, "paid": 0.0})
            amt = float(r.amount or 0)
            if r.status == "已支付":
                c["paid"] += amt
            elif r.status in ("未开票", "已开票待付"):
                c["unpaid"] += amt
        return {"month": month, "by_currency": cur}


@router.post("/po")
def create_po(body: POIn, w=Depends(require_writer),
              idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
              x_dry_run: str | None = Header(None, alias="X-Dry-Run")):
    role, name = w
    with Session(engine) as s:
        d = body.model_dump()
        if role == "agent":
            dry_run = (x_dry_run or "").lower() in {"1", "true", "yes"}
            request_hash = pending_request_hash("po", d["translator_id"], d)
            if not dry_run:
                replay = find_idempotent_request(s, name, idempotency_key, request_hash)
                if replay:
                    return replay
            legacy_replay = needs_legacy_replay_validation(s, name, idempotency_key)
            d = prepare_po(s, d, check_duplicate=not legacy_replay)
            return make_pending(s, name, "po", d["translator_id"], d,
                                idempotency_key=idempotency_key,
                                dry_run=dry_run, request_hash=request_hash)
        p = svc_create_po(s, d, name)
        s.commit()
        s.refresh(p)
        return p.as_dict()


@router.put("/po/{pid}/status")
def set_po_status(pid: int, body: StatusIn, w=Depends(require_writer),
                  idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
                  x_dry_run: str | None = Header(None, alias="X-Dry-Run")):
    role, name = w
    if body.status not in PO_STATUSES:
        raise HTTPException(400, "状态非法")
    with Session(engine) as s:
        if role == "agent":
            dry_run = (x_dry_run or "").lower() in {"1", "true", "yes"}
            request_payload = {"pid": pid, "status": body.status}
            request_hash = pending_request_hash("po_status", pid, request_payload)
            if not dry_run:
                replay = find_idempotent_request(s, name, idempotency_key, request_hash)
                if replay:
                    return replay
            po, d = prepare_po_status(s, pid, body.status)
            return make_pending(s, name, "po_status", po.translator_id, d,
                                idempotency_key=idempotency_key,
                                dry_run=dry_run, request_hash=request_hash)
        svc_set_po_status(s, pid, body.status, name)
        s.commit()
        return {"ok": True}


# ---------------- 待审队列 ----------------
@router.get("/pending")
def list_pending(who: str = Depends(require_editor)):
    with Session(engine) as s:
        rows = s.scalars(select(PendingChange).where(PendingChange.status == "pending")
                         .order_by(PendingChange.id.desc())).all()
        nm = names_of(s)
        return [{"id": r.id, "created_by": r.created_by, "kind": r.kind, "translator_id": r.translator_id,
                 "translator_name": nm.get(r.translator_id, "") if r.translator_id else "",
                 "payload": json.loads(r.payload),
                 "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None} for r in rows]


@router.post("/pending/{pcid}/approve")
def approve_pending(pcid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        claimed = s.execute(update(PendingChange).where(
            PendingChange.id == pcid,
            PendingChange.status == "pending",
        ).values(status="processing", reviewed_by=who))
        if claimed.rowcount != 1:
            s.rollback()
            raise HTTPException(404, "无此待审或已处理")
        pc = s.get(PendingChange, pcid)
        d = json.loads(pc.payload)
        if pc.kind == "rate_change":
            svc_add_rate_change(s, pc.translator_id, d, f"{who}<approve>")
        elif pc.kind == "po":
            svc_create_po(s, d, f"{who}<approve>")
        elif pc.kind == "po_status":
            svc_set_po_status(s, d["pid"], d["status"], f"{who}<approve>")
        pc.status = "approved"
        pc.reviewed_by = who
        audit(s, who, "批准", "待审", pcid, pc.kind)
        s.commit()
        return {"ok": True}


@router.post("/pending/{pcid}/reject")
def reject_pending(pcid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        rejected = s.execute(update(PendingChange).where(
            PendingChange.id == pcid,
            PendingChange.status == "pending",
        ).values(status="rejected", reviewed_by=who))
        if rejected.rowcount != 1:
            s.rollback()
            raise HTTPException(404, "无此待审或已处理")
        pc = s.get(PendingChange, pcid)
        audit(s, who, "驳回", "待审", pcid, pc.kind)
        s.commit()
        return {"ok": True}
