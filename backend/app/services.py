"""业务逻辑层：审计、汇总同步、PO、待审。HTTP 路由与"批准后执行"共用这一套。"""
import json

from fastapi import HTTPException
from sqlalchemy import select

from .models import (PO, AuditLog, Complaint, PendingChange, QualityScore,
                     RateChange, Translator)

PO_STATUSES = ["未开票", "已开票待付", "已支付", "有争议"]


def expected_amount(word_count, rate):
    """PO 金额口径：字数 ÷ 1000 × 单价（词数按字、费率按元/千字），2 位小数。"""
    return round((word_count or 0) / 1000 * (rate or 0), 2)


def get_translator(s, tid):
    t = s.get(Translator, tid)
    if not t or t.deleted_at:
        raise HTTPException(404, "译员不存在")
    return t


def names_of(s, ids=None):
    q = select(Translator.id, Translator.name).where(Translator.deleted_at.is_(None))
    if ids is not None:
        q = q.where(Translator.id.in_(ids))
    return dict(s.execute(q).all())


def audit(s, user, action, entity, eid, detail=""):
    s.add(AuditLog(user=user, action=action, entity=entity, entity_id=eid, detail=detail))


def resync_translator(s, tid):
    """按 PRD §6.3.3/§10.3.2/§12.3.2 从子记录全量重算主表派生字段（幂等，子记录变更后调用）。"""
    t = s.get(Translator, tid)
    if not t:
        return
    # 质量 §6.3.3：最近分 / 累计均分 / 低错累计
    qs = s.scalars(select(QualityScore).where(QualityScore.translator_id == tid).order_by(QualityScore.id)).all()
    scored = [float(q.score) for q in qs if q.score is not None]
    t.recent_qa_score = scored[-1] if scored else None
    t.cumulative_qa_score = round(sum(scored) / len(scored), 2) if scored else None
    t.low_error_count = sum(q.minor_errors or 0 for q in qs)
    # PO 派生：累计完成字数 / 累计未付
    pos = s.scalars(select(PO).where(PO.translator_id == tid)).all()
    t.cumulative_word_count = int(sum(float(p.word_count or 0) for p in pos))
    t.cumulative_unpaid = round(sum(float(p.amount or 0) for p in pos if p.status in ("未开票", "已开票待付")), 2)
    # 低错率 §6.3.3 = 低错数 / 累计字数(千)。约定 PO 词数单位=千字，故直接相除；若 PM 定为字需 /1000
    t.low_error_rate = round(t.low_error_count / (t.cumulative_word_count / 1000), 4) if t.cumulative_word_count else None
    # 客诉 §12.3.2：次数 / 累计扣款
    cs = s.scalars(select(Complaint).where(Complaint.translator_id == tid)).all()
    t.complaint_count = len(cs)
    t.deduction_total = round(sum(float(c.deduction_amount or 0) for c in cs), 2)
    # 谈判 §10.3.2：最近一条定状态；最近"成功"一条填谈后字段
    rcs = s.scalars(select(RateChange).where(RateChange.translator_id == tid).order_by(RateChange.change_date, RateChange.id)).all()
    if rcs:
        t.negotiation_status = rcs[-1].result or "进行中"
        succ = [r for r in rcs if r.result == "成功"]
        if succ:
            last = succ[-1]
            t.last_negotiation_date = last.change_date
            t.post_negotiation_rate = last.new_rate
            t.negotiation_notes = last.remarks
            if last.original_rate and last.new_rate is not None:
                o, nw = float(last.original_rate), float(last.new_rate)
                t.rate_reduction_pct = round((o - nw) / o * 100, 2) if o else None
                t.accepted_reduction = nw < o
    else:
        t.negotiation_status = "未启动"


def svc_add_rate_change(s, tid, d, who):
    """记一笔调价；翻译类调价同步主表当前费率。"""
    t = get_translator(s, tid)
    s.add(RateChange(translator_id=tid, change_date=d.get("change_date"), task_type=d.get("task_type"),
                     original_rate=d.get("original_rate"), new_rate=d.get("new_rate"),
                     negotiator=d.get("negotiator"), reason=d.get("reason"),
                     result=d.get("result", "成功"), remarks=d.get("remarks")))
    if d.get("task_type") == "翻译" and d.get("result", "成功") == "成功" and d.get("new_rate") is not None:
        t.translation_rate = d["new_rate"]
    audit(s, who, "新增", "报价变更", tid, f"{t.name} {d.get('task_type')} {d.get('new_rate')}")
    resync_translator(s, tid)


def svc_create_po(s, d, who):
    if d.get("po_number") and s.scalar(select(PO).where(PO.po_number == d["po_number"])):
        raise HTTPException(400, "PO 号已存在")
    amt = expected_amount(d.get("word_count"), d.get("rate"))
    p = PO(translator_id=d["translator_id"], settlement_month=d["settlement_month"], project=d.get("project"),
           role=d.get("role"), word_count=d.get("word_count"), rate=d.get("rate"), amount=amt,
           currency=d.get("currency", "CNY"), status=d.get("status", "未开票"),
           po_number=d.get("po_number"), remarks=d.get("remarks"))
    s.add(p)
    s.flush()
    audit(s, who, "新增", "PO", p.id, f"{d['settlement_month']} {amt}")
    resync_translator(s, p.translator_id)
    return p


def svc_set_po_status(s, pid, status, who):
    p = s.get(PO, pid)
    if not p:
        raise HTTPException(404, "PO 不存在")
    p.status = status
    audit(s, who, "改状态", "PO", pid, status)
    resync_translator(s, p.translator_id)


def make_pending(s, name, kind, tid, payload):
    """agent 的钱相关改动落待审队列，不直接生效。"""
    pc = PendingChange(created_by=name, kind=kind, translator_id=tid,
                       payload=json.dumps(payload, ensure_ascii=False))
    s.add(pc)
    audit(s, name, "提交建议", kind, tid, "")
    s.commit()
    s.refresh(pc)
    return {"pending": True, "pending_id": pc.id, "msg": "已提交待人工审核（钱相关需人工确认）"}
