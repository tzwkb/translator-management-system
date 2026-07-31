"""业务逻辑层：审计、汇总同步、PO、待审。HTTP 路由与"批准后执行"共用这一套。"""
import json

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .models import (PO, AuditLog, Complaint, LanguagePair, PendingChange,
                     PendingIdempotency, ProjectPrice, QualityScore, RateChange,
                     Translator, TranslatorProjectExperience)
from .pending_safety import normalize_payload, pending_fingerprint

PO_STATUSES = ["未开票", "已开票待付", "已支付", "有争议"]
DEFAULT_DAILY_OUTPUT = 2000
MONTHLY_WORK_DAYS = 20
RATE_FIELDS = {"翻译": "translation_rate", "MTPE": "mtpe_rate", "审校": "review_rate",
               "LQA": "lqa_rate", "LQE": "lqe_rate"}
LANGUAGE_OPTIONS = [
    "ZH", "ZH-HANS", "ZH-HANT", "ZH-CN", "ZH-TW", "ZH-HK",
    "EN", "EN-US", "EN-GB", "EN-AU", "EN-CA",
    "JA", "KO", "BO",
    "FR", "FR-FR", "FR-CA", "DE", "DE-DE", "ES", "ES-ES", "ES-LA", "ES-MX",
    "PT", "PT-BR", "PT-PT", "IT", "RU", "UK", "PL", "NL", "SV", "NO", "NB",
    "DA", "FI", "IS", "ET", "LV", "LT",
    "CS", "SK", "HU", "RO", "BG", "EL", "HR", "SR", "SL", "BS", "MK", "SQ",
    "TR", "AR", "HE", "FA", "UR",
    "HI", "BN", "TA", "TE", "MR", "GU", "KN", "ML", "PA", "NE", "SI",
    "TH", "VI", "ID", "MS", "TL", "FIL", "KM", "LO", "MY",
    "SW", "AF", "AM", "AZ", "BE", "CA", "EU", "GL", "KA", "KK", "KY",
    "MN", "UZ", "HY", "CY", "GA", "MT", "LA", "ZU", "XH", "YO", "IG",
    "HA", "SO", "PS", "KU", "CKB", "TG", "TK", "LB", "RW", "MG", "MI",
]
LANGUAGE_SET = set(LANGUAGE_OPTIONS)


def expected_amount(word_count, rate, pricing_mode="per_1000", amount=None):
    """按计价模式计算 PO 金额。"""
    if pricing_mode == "manual":
        return round(float(amount or 0), 2)
    if pricing_mode == "fixed":
        return round(float(amount if amount is not None else rate or 0), 2)
    if pricing_mode == "per_hour":
        return round(float(word_count or 0) * float(rate or 0), 2)
    return round(float(word_count or 0) / 1000 * float(rate or 0), 2)


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


def validate_language_pair(source_lang, target_lang, allow_same=False):
    if bool(source_lang) != bool(target_lang):
        raise HTTPException(400, "语言对需同时选择源语言和目标语言")
    if not source_lang and not target_lang:
        return None, None
    source, target = str(source_lang).strip().upper(), str(target_lang).strip().upper()
    if source not in LANGUAGE_SET or target not in LANGUAGE_SET:
        opts = "、".join(LANGUAGE_OPTIONS)
        raise HTTPException(400, f"语言不在固定选项中：{opts}")
    if source == target and not allow_same:
        raise HTTPException(400, "源语言和目标语言不能相同")
    return source, target


def prepare_rate_change(s, tid, payload):
    get_translator(s, tid)
    data = normalize_payload(dict(payload))
    source_lang, target_lang = validate_language_pair(
        data.get("source_lang"), data.get("target_lang"),
    )
    data["source_lang"] = source_lang
    data["target_lang"] = target_lang
    return data


def prepare_project_experience(s, tid, payload):
    get_translator(s, tid)
    data = normalize_payload(dict(payload))
    source_lang, target_lang = validate_language_pair(
        data.get("source_lang"), data.get("target_lang"),
        allow_same=data.get("role") in {"LQA", "LQE"},
    )
    data["source_lang"] = source_lang
    data["target_lang"] = target_lang
    return data


def _po_price_payload(price):
    unit = price.unit
    if price.price_type == "fixed" or unit in {"project", "task"}:
        return {"pricing_mode": "fixed", "amount": float(price.amount), "rate": None}
    if unit == "hour":
        return {"pricing_mode": "per_hour", "rate": float(price.amount), "amount": None}
    if unit == "word":
        return {
            "pricing_mode": "per_1000",
            "rate": round(float(price.amount) * 1000, 6),
            "amount": None,
        }
    if unit == "per_1000":
        return {"pricing_mode": "per_1000", "rate": float(price.amount), "amount": None}
    return {"pricing_mode": "manual", "amount": float(price.amount), "rate": None}


def match_po_price(
    s,
    translator_id,
    project=None,
    role=None,
    source_lang=None,
    target_lang=None,
    currency=None,
):
    project_name = str(project or "").strip()
    currency_code = str(currency or "").strip().upper()
    candidates = s.scalars(
        select(ProjectPrice)
        .where(ProjectPrice.translator_id == translator_id)
        .order_by(ProjectPrice.id.desc())
    ).all()
    matches = []
    for price in candidates:
        if project_name and price.project_name.casefold() != project_name.casefold():
            continue
        if currency_code and price.currency != currency_code:
            continue
        if role == "一口价" and price.price_type != "fixed":
            continue
        if role == "其他" and price.price_type != "custom":
            continue
        if role not in {None, "", "一口价", "其他"} and price.task_type != role:
            continue
        language_score = 0
        if source_lang and target_lang:
            if price.source_lang == source_lang and price.target_lang == target_lang:
                language_score = 2
            elif not price.source_lang and not price.target_lang:
                language_score = 1
            else:
                continue
        elif price.source_lang or price.target_lang:
            continue
        matches.append((language_score, price.id, price))
    if matches:
        price = max(matches, key=lambda item: (item[0], item[1]))[2]
        return {
            "matched": True,
            "source": "project_price",
            "project_price_id": price.id,
            "currency": price.currency,
            "unit": price.unit,
            **_po_price_payload(price),
        }
    if source_lang and target_lang:
        language_pair = find_language_pair(
            s, translator_id, source_lang, target_lang,
        )
        rate = rate_for_role(language_pair, role)
        if rate is not None:
            return {
                "matched": True,
                "source": "language_pair",
                "language_pair_id": language_pair.id,
                "currency": language_pair.currency or currency_code or "CNY",
                "pricing_mode": "per_hour" if role in {"LQA", "LQE"} else "per_1000",
                "rate": float(rate),
                "amount": None,
            }
    return {"matched": False}


def prepare_po(s, payload, check_duplicate=True, exclude_po_id=None):
    data = normalize_payload(dict(payload))
    get_translator(s, data["translator_id"])
    if check_duplicate and data.get("po_number"):
        query = select(PO.id).where(PO.po_number == data["po_number"])
        if exclude_po_id is not None:
            query = query.where(PO.id != exclude_po_id)
        if s.scalar(query):
            raise HTTPException(400, "PO 号已存在")
    if check_duplicate and data.get("source_key"):
        query = select(PO.id).where(PO.source_key == data["source_key"])
        if exclude_po_id is not None:
            query = query.where(PO.id != exclude_po_id)
        if s.scalar(query):
            raise HTTPException(400, "来源行已导入")
    source_lang, target_lang = validate_language_pair(
        data.get("source_lang"), data.get("target_lang"),
        allow_same=data.get("role") in {"LQA", "LQE"},
    )
    data["source_lang"] = source_lang
    data["target_lang"] = target_lang
    if data.get("rate") is None and data.get("amount") is None:
        matched = match_po_price(
            s,
            data["translator_id"],
            data.get("project"),
            data.get("role"),
            source_lang,
            target_lang,
            data.get("currency"),
        )
        if matched["matched"]:
            for key in ("pricing_mode", "rate", "amount", "currency"):
                if key in matched:
                    data[key] = matched[key]
    return normalize_payload(data)


def svc_add_project_experience(s, tid, payload, who):
    data = prepare_project_experience(s, tid, payload)
    translator = get_translator(s, tid)
    experience = TranslatorProjectExperience(translator_id=tid, **data)
    s.add(experience)
    s.flush()
    audit(
        s, who, "新增", "项目经历", experience.id,
        f"{translator.name} {experience.project_name}",
    )
    return experience


def get_project_experience(s, tid, experience_id):
    translator = get_translator(s, tid)
    experience = s.get(TranslatorProjectExperience, experience_id)
    if not experience or experience.translator_id != tid:
        raise HTTPException(404, "项目经历不存在")
    return translator, experience


def svc_update_project_experience(s, tid, experience_id, payload, who):
    data = prepare_project_experience(s, tid, payload)
    translator, experience = get_project_experience(s, tid, experience_id)
    for key, value in data.items():
        setattr(experience, key, value)
    audit(
        s, who, "编辑", "项目经历", experience.id,
        f"{translator.name} {experience.project_name}",
    )
    return experience


def svc_delete_project_experience(s, tid, experience_id, who):
    translator, experience = get_project_experience(s, tid, experience_id)
    audit(
        s, who, "删除", "项目经历", experience.id,
        f"{translator.name} {experience.project_name}",
    )
    s.delete(experience)


def prepare_po_status(s, pid, status):
    if status not in PO_STATUSES:
        raise HTTPException(400, "状态非法")
    po = s.get(PO, pid)
    if not po:
        raise HTTPException(404, "PO 不存在")
    return po, {"pid": pid, "status": status}


def language_pair_options():
    return [{"source_lang": s, "target_lang": t, "label": f"{s}→{t}"}
            for s in LANGUAGE_OPTIONS for t in LANGUAGE_OPTIONS if s != t]


def find_language_pair(s, tid, source_lang, target_lang):
    if not source_lang or not target_lang:
        return None
    return s.scalar(select(LanguagePair).where(
        LanguagePair.translator_id == tid,
        LanguagePair.source_lang == source_lang,
        LanguagePair.target_lang == target_lang,
    ))


def get_or_create_language_pair(s, tid, source_lang, target_lang):
    lp = find_language_pair(s, tid, source_lang, target_lang)
    if lp:
        return lp
    lp = LanguagePair(translator_id=tid, source_lang=source_lang, target_lang=target_lang)
    s.add(lp)
    s.flush()
    return lp


def rate_for_role(lp, role):
    field = RATE_FIELDS.get(role or "")
    return getattr(lp, field) if lp and field else None


def quality_rating(score):
    if score is None:
        return None
    value = float(score)
    if value >= 95:
        return "S"
    if value >= 90:
        return "A"
    if value >= 85:
        return "A-"
    if value >= 80:
        return "B"
    if value >= 60:
        return "C"
    return "D"


def resync_quality_summary(s, tid):
    t = s.get(Translator, tid)
    if not t:
        return
    qs = s.scalars(
        select(QualityScore)
        .where(QualityScore.translator_id == tid)
        .order_by(QualityScore.id)
    ).all()
    scored = [
        float(q.score)
        for q in qs
        if q.score is not None and (q.qa_type or "").strip().upper() == "LQE"
    ]
    t.recent_qa_score = scored[-1] if scored else None
    t.cumulative_qa_score = (
        round(sum(scored) / len(scored), 2) if scored else None
    )
    t.internal_rating = t.manual_rating or quality_rating(t.cumulative_qa_score)
    t.low_error_count = sum(q.minor_errors or 0 for q in qs)


def resync_translator(s, tid):
    """按 PRD §6.3.3/§10.3.2/§12.3.2 从子记录全量重算主表派生字段（幂等，子记录变更后调用）。"""
    t = s.get(Translator, tid)
    if not t:
        return
    # 质量 §6.3.3：最近分 / 累计均分 / 自动评级 / 低错累计
    resync_quality_summary(s, tid)
    # PO 派生：累计完成字数 / 累计未付
    pos = s.scalars(select(PO).where(PO.translator_id == tid)).all()
    t.cumulative_word_count = int(sum(float(p.word_count or 0) for p in pos))
    t.cumulative_unpaid = round(sum(float(p.amount or 0) for p in pos if p.status in ("未开票", "已开票待付")), 2)
    # 低错率 §6.3.3 = 低错数 / 累计字数(千)；PO word_count 存实际字数。
    t.low_error_rate = round(t.low_error_count / (t.cumulative_word_count / 1000), 4) if t.cumulative_word_count else None
    # 客诉 §12.3.2：次数 / 累计扣款
    cs = s.scalars(select(Complaint).where(Complaint.translator_id == tid)).all()
    t.complaint_count = len(cs)
    t.deduction_total = round(sum(float(c.deduction_amount or 0) for c in cs), 2)
    # 谈判 §10.3.2：最近一条定状态；最近"成功"一条填谈后字段
    rcs = s.scalars(select(RateChange).where(RateChange.translator_id == tid).order_by(RateChange.change_date, RateChange.id)).all()
    t.last_negotiation_date = None
    t.post_negotiation_rate = None
    t.negotiation_notes = None
    t.rate_reduction_pct = None
    t.accepted_reduction = None
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


def availability_snapshot(translator, projects, today=None):
    """按当前项目量和固定 20 个工作日计算月度产能，不覆盖人工档期。"""
    total_load = 0.0
    basis = []
    daily_capacity = float(translator.daily_output or DEFAULT_DAILY_OUTPUT)
    monthly_capacity = daily_capacity * MONTHLY_WORK_DAYS
    for project in projects:
        if project.project_status != "current":
            continue
        if project.remaining_volume is None:
            continue
        role = project.role or "翻译"
        remaining = float(project.remaining_volume)
        load_pct = remaining / max(1.0, monthly_capacity) * 100
        total_load += load_pct
        basis.append({
            "project_id": project.id,
            "project_name": project.project_name,
            "role": role,
            "remaining_volume": remaining,
            "deadline": project.deadline,
            "work_days": MONTHLY_WORK_DAYS,
            "daily_capacity": daily_capacity,
            "monthly_capacity": monthly_capacity,
            "load_pct": round(load_pct, 2),
        })
    computed = None
    if basis:
        if total_load < 50:
            computed = "空闲"
        elif total_load < 80:
            computed = "健康"
        elif total_load <= 100:
            computed = "饱和"
        else:
            computed = "警告"
    return {
        "computed_availability": computed,
        "computed_load_pct": round(total_load, 2) if basis else None,
        "availability_conflict": bool(
            computed and translator.availability and computed != translator.availability
        ),
        "availability_basis": basis,
    }


def svc_add_rate_change(s, tid, d, who):
    """记一笔调价；带语言对时更新该语言对费率，否则保留旧的主表同步口径。"""
    d = prepare_rate_change(s, tid, d)
    t = get_translator(s, tid)
    source_lang, target_lang = d.get("source_lang"), d.get("target_lang")
    s.add(RateChange(translator_id=tid, change_date=d.get("change_date"), task_type=d.get("task_type"),
                     source_lang=source_lang, target_lang=target_lang,
                     original_rate=d.get("original_rate"), new_rate=d.get("new_rate"),
                     negotiator=d.get("negotiator"), reason=d.get("reason"),
                     result=d.get("result", "成功"), remarks=d.get("remarks")))
    if d.get("result", "成功") == "成功" and d.get("new_rate") is not None:
        field = RATE_FIELDS.get(d.get("task_type") or "")
        if source_lang and target_lang and field:
            lp = get_or_create_language_pair(s, tid, source_lang, target_lang)
            setattr(lp, field, d["new_rate"])
            if d.get("currency"):
                lp.currency = d["currency"]
            lp.rate_confirmed_date = d.get("change_date") or lp.rate_confirmed_date
        elif d.get("task_type") == "翻译":
            t.translation_rate = d["new_rate"]
    pair = f" {source_lang}→{target_lang}" if source_lang and target_lang else ""
    audit(s, who, "新增", "报价变更", tid, f"{t.name}{pair} {d.get('task_type')} {d.get('new_rate')}")
    resync_translator(s, tid)


def svc_create_po(s, d, who):
    d = prepare_po(s, d)
    source_lang, target_lang = d.get("source_lang"), d.get("target_lang")
    pricing_mode = d.get("pricing_mode") or "per_1000"
    amt = expected_amount(
        d.get("word_count"), d.get("rate"), pricing_mode, d.get("amount"),
    )
    p = PO(translator_id=d["translator_id"], settlement_month=d["settlement_month"], project=d.get("project"),
           source_lang=source_lang, target_lang=target_lang, role=d.get("role"),
           word_count=d.get("word_count"), rate=d.get("rate"), amount=amt,
           currency=d.get("currency", "CNY"), status=d.get("status", "未开票"),
           po_number=d.get("po_number"), pricing_mode=pricing_mode,
           source_key=d.get("source_key"), source_name=d.get("source_name"),
           source_row=d.get("source_row"), remarks=d.get("remarks"))
    s.add(p)
    s.flush()
    audit(s, who, "新增", "PO", p.id, f"{d['settlement_month']} {amt}")
    resync_translator(s, p.translator_id)
    return p


def svc_update_po(s, pid, d, who):
    p = s.get(PO, pid)
    if not p:
        raise HTTPException(404, "PO 不存在")
    data = dict(d)
    for key in ("source_key", "source_name", "source_row"):
        if not data.get(key):
            data[key] = getattr(p, key)
    prepared = prepare_po(s, data, exclude_po_id=pid)
    old_translator_id = p.translator_id
    pricing_mode = prepared.get("pricing_mode") or "per_1000"
    amount = expected_amount(
        prepared.get("word_count"),
        prepared.get("rate"),
        pricing_mode,
        prepared.get("amount"),
    )
    for key in (
        "translator_id", "settlement_month", "project", "source_lang",
        "target_lang", "role", "word_count", "rate", "currency", "status",
        "po_number", "pricing_mode", "source_key", "source_name", "source_row",
        "remarks",
    ):
        setattr(p, key, prepared.get(key))
    p.amount = amount
    audit(s, who, "人工修正", "PO", pid, f"{p.settlement_month} {amount}")
    resync_translator(s, old_translator_id)
    if p.translator_id != old_translator_id:
        resync_translator(s, p.translator_id)
    return p


def svc_set_po_status(s, pid, status, who):
    p, _ = prepare_po_status(s, pid, status)
    p.status = status
    audit(s, who, "改状态", "PO", pid, status)
    resync_translator(s, p.translator_id)


def preview_pending(kind, tid, payload):
    return {"dry_run": True, "kind": kind, "translator_id": tid, "payload": payload,
            "msg": "预演完成，未写入待审队列"}


def _existing_pending_response(pc, message):
    return {"pending": pc.status == "pending", "pending_id": pc.id, "status": pc.status,
            "deduplicated": True, "msg": message}


def pending_request_hash(kind, target_id, payload):
    return pending_fingerprint(f"request:{kind}", target_id, payload)


def find_idempotent_request(s, name, idempotency_key, request_hash,
                            candidate_payload_hash=None):
    key = (idempotency_key or "").strip() or None
    if key and len(key) > 160:
        raise HTTPException(400, "Idempotency-Key 不能超过 160 个字符")
    if not key:
        return None
    binding = s.scalar(select(PendingIdempotency).where(
        PendingIdempotency.created_by == name,
        PendingIdempotency.idempotency_key == key,
    ))
    if not binding:
        return None
    if binding.request_hash is None:
        if candidate_payload_hash is None:
            return None
        existing = s.get(PendingChange, binding.pending_change_id)
        if not existing:
            raise HTTPException(409, "幂等键对应的待审记录不存在")
        if existing.payload_hash != candidate_payload_hash:
            raise HTTPException(409, "幂等键已被其他操作内容使用")
        claimed = s.execute(update(PendingIdempotency).where(
            PendingIdempotency.id == binding.id,
            PendingIdempotency.request_hash.is_(None),
        ).values(request_hash=request_hash))
        if claimed.rowcount == 1:
            s.commit()
            return _existing_pending_response(existing, "重复请求，已返回原待审记录")
        s.rollback()
        binding = s.get(PendingIdempotency, binding.id)
        if not binding or binding.request_hash != request_hash:
            raise HTTPException(409, "幂等键已被其他操作内容使用")
    elif binding.request_hash != request_hash:
        raise HTTPException(409, "幂等键已被其他操作内容使用")
    existing = s.get(PendingChange, binding.pending_change_id)
    if not existing:
        raise HTTPException(409, "幂等键对应的待审记录不存在")
    return _existing_pending_response(existing, "重复请求，已返回原待审记录")


def needs_legacy_replay_validation(s, name, idempotency_key):
    key = (idempotency_key or "").strip() or None
    if not key:
        return False
    return s.scalar(select(PendingIdempotency.id).where(
        PendingIdempotency.created_by == name,
        PendingIdempotency.idempotency_key == key,
        PendingIdempotency.request_hash.is_(None),
    )) is not None


def _bind_existing_pending(s, name, key, request_hash, pending_change_id,
                           candidate_payload_hash):
    if not key:
        return
    replay = find_idempotent_request(
        s, name, key, request_hash,
        candidate_payload_hash=candidate_payload_hash,
    )
    if replay:
        return
    s.add(PendingIdempotency(created_by=name, idempotency_key=key,
                             request_hash=request_hash,
                             pending_change_id=pending_change_id))
    try:
        s.commit()
    except IntegrityError as exc:
        s.rollback()
        replay = find_idempotent_request(
            s, name, key, request_hash,
            candidate_payload_hash=candidate_payload_hash,
        )
        if not replay:
            raise exc


def make_pending(s, name, kind, tid, payload, idempotency_key=None, dry_run=False,
                 request_hash=None):
    """agent 的钱相关改动预演或落待审队列，并阻止重复写入。"""
    key = (idempotency_key or "").strip() or None
    if key and len(key) > 160:
        raise HTTPException(400, "Idempotency-Key 不能超过 160 个字符")
    if dry_run:
        return preview_pending(kind, tid, payload)

    payload = normalize_payload(payload)
    fingerprint = pending_fingerprint(kind, tid, payload)
    request_hash = request_hash or fingerprint
    if key:
        existing_response = find_idempotent_request(
            s, name, key, request_hash,
            candidate_payload_hash=fingerprint,
        )
        if existing_response:
            return existing_response

    existing = s.scalar(select(PendingChange).where(
        PendingChange.status == "pending",
        PendingChange.kind == kind,
        PendingChange.translator_id == tid,
        PendingChange.payload_hash == fingerprint,
    ).order_by(PendingChange.id))
    if existing:
        _bind_existing_pending(s, name, key, request_hash, existing.id, fingerprint)
        return _existing_pending_response(existing, "相同内容已在待审队列中")

    pc = PendingChange(created_by=name, kind=kind, translator_id=tid,
                       payload=json.dumps(payload, ensure_ascii=False),
                       idempotency_key=key, request_hash=request_hash,
                       payload_hash=fingerprint)
    s.add(pc)
    try:
        s.flush()
        if key:
            s.add(PendingIdempotency(created_by=name, idempotency_key=key,
                                     request_hash=request_hash,
                                     pending_change_id=pc.id))
        audit(s, name, "提交建议", kind, tid, "")
        s.commit()
    except IntegrityError as exc:
        s.rollback()
        if key:
            replay = find_idempotent_request(
                s, name, key, request_hash,
                candidate_payload_hash=fingerprint,
            )
            if replay:
                return replay
        existing = s.scalar(select(PendingChange).where(
            PendingChange.status == "pending",
            PendingChange.payload_hash == fingerprint,
        ))
        if existing:
            _bind_existing_pending(s, name, key, request_hash, existing.id, fingerprint)
            return _existing_pending_response(existing, "相同内容已在待审队列中")
        raise
    s.refresh(pc)
    return {"pending": True, "pending_id": pc.id, "status": "pending",
            "deduplicated": False, "msg": "已提交待人工审核（钱相关需人工确认）"}
