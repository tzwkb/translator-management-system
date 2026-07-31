"""译员主表及其子表接口。"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from ..db import engine
from ..file_storage import (IMAGE_EXTENSIONS, remove_stored, save_upload,
                            stored_path)
from ..models import (CapacityMonthOverride, Complaint, Contract, LanguagePair,
                      PaymentAccount, PaymentInfo, ProjectPrice, QualityScore,
                      RateChange, Translator, TranslatorAlias, TranslatorAttachment,
                      TranslatorProjectExperience)
from ..schemas import (CapacityOverrideIn, ComplaintIn, ContractIn, LanguagePairIn,
                       PaymentAccountIn, PaymentIn, ProjectExperienceIn,
                       ProjectPriceIn, QualityIn, RateChangeIn, TranslatorIn)
from ..schemas import TranslatorAliasIn
from ..security import dec, enc, require_authenticated, require_editor, require_writer
from ..services import (audit, availability_snapshot, find_language_pair,
                        get_translator,
                        find_idempotent_request, language_pair_options,
                        make_pending, pending_request_hash, prepare_rate_change,
                        resync_translator, svc_add_rate_change,
                        svc_add_project_experience,
                        svc_delete_project_experience,
                        svc_update_project_experience, validate_language_pair,
                        normalize_capacity_month)
from ..translator_identity import (
    add_translator_alias,
    assert_name_not_reserved,
    normalize_translator_name,
)
from ..translator_filters import (
    FILTER_FIELDS,
    load_related_filter_rows,
    matches_filter_conditions,
    parse_filter_conditions,
)

router = APIRouter(prefix="/api")


@router.get("/language-pair-options")
def list_language_pair_options():
    return language_pair_options()


@router.get("/translator-filter-fields")
def list_translator_filter_fields():
    return FILTER_FIELDS


# ---------------- 译员 ----------------
@router.get("/translators")
def list_translators(
    q: str | None = None,
    source_lang: str | None = None,
    target_lang: str | None = None,
    native_language: str | None = None,
    rate_type: str | None = None,
    min_rate: float | None = None,
    max_rate: float | None = None,
    currency: str | None = None,
    domain: str | None = None,
    has_wechat: bool | None = None,
    rating: str | None = None,
    gender: str | None = None,
    entity_type: str | None = None,
    availability: str | None = None,
    capacity_month: str | None = None,
    filters: str | None = None,
    page: int = 1,
    page_size: int = 50,
    paged: bool = False,
):
    if min_rate is not None and max_rate is not None and min_rate > max_rate:
        raise HTTPException(400, "最低价格不能大于最高价格")
    if (min_rate is not None or max_rate is not None) and (not rate_type or not currency):
        raise HTTPException(400, "价格区间必须同时指定价格类型和币种")
    rate_fields = {
        "translation": "translation_rate",
        "翻译": "translation_rate",
        "mtpe": "mtpe_rate",
        "MTPE": "mtpe_rate",
        "review": "review_rate",
        "审校": "review_rate",
        "lqa": "lqa_rate",
        "LQA": "lqa_rate",
        "lqe": "lqe_rate",
        "LQE": "lqe_rate",
    }
    if rate_type and rate_type not in rate_fields and rate_type not in {"fixed", "custom"}:
        raise HTTPException(400, "价格类型非法")
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(400, "分页参数非法")
    generic_conditions = parse_filter_conditions(filters)
    try:
        selected_capacity_month, _ = normalize_capacity_month(capacity_month)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    with Session(engine) as s:
        rows = s.scalars(select(Translator).where(Translator.deleted_at.is_(None)).order_by(Translator.id)).all()
        tids = [r.id for r in rows]
        lp_map: dict[int, list[LanguagePair]] = {}
        if tids:
            lps = s.scalars(select(LanguagePair).where(LanguagePair.translator_id.in_(tids)).order_by(LanguagePair.id)).all()
            for lp in lps:
                lp_map.setdefault(lp.translator_id, []).append(lp)
        alias_map: dict[int, list[TranslatorAlias]] = {}
        if tids:
            aliases = s.scalars(
                select(TranslatorAlias)
                .where(TranslatorAlias.translator_id.in_(tids))
                .order_by(TranslatorAlias.id)
            ).all()
            for alias in aliases:
                alias_map.setdefault(alias.translator_id, []).append(alias)
        project_map: dict[int, list[TranslatorProjectExperience]] = {}
        if tids:
            projects = s.scalars(
                select(TranslatorProjectExperience)
                .where(
                    TranslatorProjectExperience.translator_id.in_(tids),
                    TranslatorProjectExperience.project_status == "current",
                )
                .order_by(
                    TranslatorProjectExperience.start_date.is_(None),
                    TranslatorProjectExperience.start_date.desc(),
                    TranslatorProjectExperience.id.desc(),
                )
            ).all()
            for project in projects:
                project_map.setdefault(project.translator_id, []).append(project)
        capacity_override_map: dict[int, CapacityMonthOverride] = {}
        if tids:
            capacity_overrides = s.scalars(
                select(CapacityMonthOverride).where(
                    CapacityMonthOverride.translator_id.in_(tids),
                    CapacityMonthOverride.month == selected_capacity_month,
                )
            ).all()
            capacity_override_map = {
                item.translator_id: item for item in capacity_overrides
            }
        price_map: dict[int, list[ProjectPrice]] = {}
        if tids and rate_type in {"fixed", "custom"}:
            prices = s.scalars(
                select(ProjectPrice).where(ProjectPrice.translator_id.in_(tids))
            ).all()
            for price in prices:
                price_map.setdefault(price.translator_id, []).append(price)
        related_filter_rows = (
            load_related_filter_rows(s, tids) if generic_conditions else {}
        )

        def _tags(value):
            return {
                item.strip().casefold()
                for item in re.split(r"[,，;；、]", value or "")
                if item.strip()
            }

        def _pair_matches(pair):
            return (
                (not source_lang or pair.source_lang == source_lang.strip().upper())
                and (not target_lang or pair.target_lang == target_lang.strip().upper())
            )

        result = []
        for r in rows:
            translator_pairs = lp_map.get(r.id, [])
            translator_projects = project_map.get(r.id, [])
            snapshot = availability_snapshot(
                r,
                translator_projects,
                month=selected_capacity_month,
                override=capacity_override_map.get(r.id),
            )
            r._cached_lp = ", ".join(
                f"{pair.source_lang}→{pair.target_lang}" for pair in translator_pairs
            )
            r._cached_current_projects = [
                project.as_dict() for project in translator_projects
            ]
            r._cached_aliases = [
                alias.alias for alias in alias_map.get(r.id, [])
            ]
            r._computed_availability = snapshot["computed_availability"]
            r._computed_load_pct = snapshot["computed_load_pct"]
            r._capacity_month = snapshot["capacity_month"]
            r._effective_availability = snapshot["effective_availability"]
            r._capacity_override_status = (
                snapshot["capacity_override"]["status"]
                if snapshot["capacity_override"] else None
            )
            r._capacity_override_reason = (
                snapshot["capacity_override"]["reason"]
                if snapshot["capacity_override"] else None
            )
            r._availability_conflict = snapshot["availability_conflict"]
            r._availability_basis = snapshot["availability_basis"]
            r._capacity_data_complete = snapshot["capacity_data_complete"]
            r._capacity_issues = snapshot["capacity_issues"]

            if (source_lang or target_lang) and not any(
                _pair_matches(pair) for pair in translator_pairs
            ):
                continue
            if native_language and (r.native_language or "").casefold() != native_language.strip().casefold():
                continue
            if domain and domain.strip().casefold() not in _tags(r.domains):
                continue
            if has_wechat is not None and bool((r.wechat or "").strip()) != has_wechat:
                continue
            if rating and r.internal_rating != rating:
                continue
            if gender and r.gender != gender:
                continue
            if entity_type and r.entity_type != entity_type:
                continue
            effective_availability = snapshot["effective_availability"]
            if availability and effective_availability != availability:
                continue
            if rate_type:
                values = []
                if rate_type in {"fixed", "custom"}:
                    values = [
                        float(price.amount)
                        for price in price_map.get(r.id, [])
                        if price.price_type == rate_type
                        and (not currency or price.currency == currency)
                        and (not source_lang or price.source_lang == source_lang.strip().upper())
                        and (not target_lang or price.target_lang == target_lang.strip().upper())
                    ]
                else:
                    field = rate_fields[rate_type]
                    values = [
                        float(value)
                        for pair in translator_pairs
                        if _pair_matches(pair)
                        and (not currency or pair.currency == currency)
                        and (value := getattr(pair, field)) is not None
                    ]
                if not values:
                    continue
                if (min_rate is not None or max_rate is not None) and not any(
                    (min_rate is None or value >= min_rate)
                    and (max_rate is None or value <= max_rate)
                    for value in values
                ):
                    continue
            if q:
                needle = q.strip().casefold()
                haystack = " ".join([
                    r.name or "",
                    " ".join(r._cached_aliases),
                    r._cached_lp,
                    " ".join(project.project_name for project in translator_projects),
                ]).casefold()
                if needle not in haystack:
                    continue
            record = r.as_dict()
            if generic_conditions and not matches_filter_conditions(
                record,
                related_filter_rows.get(r.id, {}),
                generic_conditions,
            ):
                continue
            result.append(record)
        total = len(result)
        if not paged:
            return result
        start = (page - 1) * page_size
        return {
            "items": result[start:start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.post("/translators")
def create_translator(body: TranslatorIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        if body.email and s.scalar(select(Translator).where(Translator.email == body.email, Translator.deleted_at.is_(None))):
            raise HTTPException(400, "邮箱已存在")
        try:
            assert_name_not_reserved(s, body.name)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        t = Translator(**body.model_dump(exclude={"internal_rating"}))
        s.add(t)
        s.flush()
        resync_translator(s, t.id)
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
        old_name = t.name
        try:
            assert_name_not_reserved(s, body.name, tid)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        for k, v in body.model_dump(exclude={"internal_rating"}).items():
            setattr(t, k, v)
        if normalize_translator_name(old_name) != normalize_translator_name(t.name):
            try:
                add_translator_alias(s, tid, old_name)
            except ValueError as error:
                raise HTTPException(400, str(error)) from error
        resync_translator(s, tid)
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


def child_or_404(s: Session, model, tid: int, cid: int, label: str):
    get_translator(s, tid)
    row = s.get(model, cid)
    if not row or row.translator_id != tid:
        raise HTTPException(404, f"{label}不存在")
    return row


# ---------------- 名称映射 ----------------
@router.get("/translators/{tid}/aliases")
def list_translator_aliases(tid: int):
    with Session(engine) as s:
        get_translator(s, tid)
        rows = s.scalars(
            select(TranslatorAlias)
            .where(TranslatorAlias.translator_id == tid)
            .order_by(TranslatorAlias.id)
        ).all()
        return [row.as_dict() for row in rows]


@router.post("/translators/{tid}/aliases")
def create_translator_alias(
    tid: int,
    body: TranslatorAliasIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        get_translator(s, tid)
        try:
            row, created = add_translator_alias(s, tid, body.alias)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        if row is None:
            raise HTTPException(400, "名称映射不能与当前姓名相同")
        if created:
            audit(s, who, "新增", "译员名称映射", row.id, body.alias)
            s.commit()
            s.refresh(row)
        return row.as_dict()


@router.put("/translators/{tid}/aliases/{alias_id}")
def update_translator_alias(
    tid: int,
    alias_id: int,
    body: TranslatorAliasIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        translator = get_translator(s, tid)
        row = child_or_404(s, TranslatorAlias, tid, alias_id, "名称映射")
        normalized = normalize_translator_name(body.alias)
        if normalize_translator_name(translator.name) == normalized:
            raise HTTPException(400, "名称映射不能与当前姓名相同")
        canonical_conflict = any(
            normalize_translator_name(item.name) == normalized
            for item in s.scalars(
                select(Translator).where(
                    Translator.deleted_at.is_(None),
                    Translator.id != tid,
                )
            ).all()
        )
        alias_conflict = s.scalar(
            select(TranslatorAlias).where(
                TranslatorAlias.normalized_alias == normalized,
                TranslatorAlias.id != alias_id,
            )
        )
        if canonical_conflict:
            raise HTTPException(400, "该名称与其他译员的当前姓名重复")
        if alias_conflict:
            raise HTTPException(400, "该名称已存在映射")
        row.alias = body.alias
        row.normalized_alias = normalized
        audit(s, who, "编辑", "译员名称映射", row.id, body.alias)
        s.commit()
        s.refresh(row)
        return row.as_dict()


@router.delete("/translators/{tid}/aliases/{alias_id}")
def delete_translator_alias(
    tid: int,
    alias_id: int,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = child_or_404(s, TranslatorAlias, tid, alias_id, "名称映射")
        detail = row.alias
        s.delete(row)
        audit(s, who, "删除", "译员名称映射", alias_id, detail)
        s.commit()
        return {"ok": True}


# ---------------- 项目经历 ----------------
@router.get("/translators/{tid}/project-experiences")
def list_project_experiences(tid: int):
    with Session(engine) as s:
        get_translator(s, tid)
        current_first = case(
            (TranslatorProjectExperience.project_status == "current", 0),
            else_=1,
        )
        rows = s.scalars(
            select(TranslatorProjectExperience)
            .where(TranslatorProjectExperience.translator_id == tid)
            .order_by(
                current_first,
                TranslatorProjectExperience.start_date.is_(None),
                TranslatorProjectExperience.start_date.desc(),
                TranslatorProjectExperience.id.desc(),
            )
        ).all()
        return [row.as_dict() for row in rows]


@router.post("/translators/{tid}/project-experiences")
def add_project_experience(
    tid: int,
    body: ProjectExperienceIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        experience = svc_add_project_experience(s, tid, body.model_dump(), who)
        s.commit()
        s.refresh(experience)
        return experience.as_dict()


@router.put("/translators/{tid}/project-experiences/{experience_id}")
def update_project_experience(
    tid: int,
    experience_id: int,
    body: ProjectExperienceIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        experience = svc_update_project_experience(
            s, tid, experience_id, body.model_dump(), who,
        )
        s.commit()
        s.refresh(experience)
        return experience.as_dict()


@router.delete("/translators/{tid}/project-experiences/{experience_id}")
def delete_project_experience(
    tid: int,
    experience_id: int,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        svc_delete_project_experience(s, tid, experience_id, who)
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
def add_rate_change(tid: int, body: RateChangeIn, w=Depends(require_writer),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
                    x_dry_run: str | None = Header(None, alias="X-Dry-Run")):
    role, name = w
    with Session(engine) as s:
        d = body.model_dump()
        if role == "agent":
            dry_run = (x_dry_run or "").lower() in {"1", "true", "yes"}
            request_hash = pending_request_hash("rate_change", tid, d)
            if not dry_run:
                replay = find_idempotent_request(s, name, idempotency_key, request_hash)
                if replay:
                    return replay
            d = prepare_rate_change(s, tid, d)
            return make_pending(s, name, "rate_change", tid, d,
                                idempotency_key=idempotency_key,
                                dry_run=dry_run, request_hash=request_hash)
        svc_add_rate_change(s, tid, d, name)
        s.commit()
        return {"ok": True}


@router.delete("/translators/{tid}/rate-changes/{rid}")
def delete_rate_change(tid: int, rid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        r = child_or_404(s, RateChange, tid, rid, "报价变更")
        audit(s, who, "删除", "报价变更", tid, f"{r.change_date} {r.task_type or ''}")
        s.delete(r)
        resync_translator(s, tid)
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


@router.delete("/translators/{tid}/quality/{qid}")
def delete_quality(tid: int, qid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        q = child_or_404(s, QualityScore, tid, qid, "质量记分")
        audit(s, who, "删除", "质量记分", tid, f"{q.evaluation_period or ''} {q.score or ''}")
        s.delete(q)
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


@router.delete("/translators/{tid}/contracts/{cid}")
def delete_contract(tid: int, cid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        c = child_or_404(s, Contract, tid, cid, "合同")
        audit(s, who, "删除", "合同", tid, c.contract_number or "")
        s.delete(c)
        s.commit()
        return {"ok": True}


# ---------------- 语言对 ----------------
@router.get("/translators/{tid}/language-pairs")
def list_language_pairs(tid: int):
    with Session(engine) as s:
        rows = s.scalars(select(LanguagePair).where(LanguagePair.translator_id == tid).order_by(LanguagePair.id)).all()
        return [r.as_dict() for r in rows]


@router.post("/translators/{tid}/language-pairs")
def add_language_pair(tid: int, body: LanguagePairIn, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        source_lang, target_lang = validate_language_pair(body.source_lang, body.target_lang)
        data = body.model_dump()
        data["source_lang"], data["target_lang"] = source_lang, target_lang
        lp = find_language_pair(s, tid, source_lang, target_lang)
        action = "编辑" if lp else "新增"
        if lp:
            for k in ("translation_rate", "mtpe_rate", "review_rate", "lqa_rate",
                      "lqe_rate", "currency", "rate_confirmed_date"):
                v = data.get(k)
                if v is not None:
                    setattr(lp, k, v)
        else:
            lp = LanguagePair(translator_id=tid, **data)
            s.add(lp)
        audit(s, who, action, "语言对", tid, f"{lp.source_lang}→{lp.target_lang}")
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


# ---------------- 项目专用价格 ----------------
def _project_price_data(s: Session, tid: int, body: ProjectPriceIn):
    get_translator(s, tid)
    data = body.model_dump()
    source_lang, target_lang = validate_language_pair(
        data.get("source_lang"), data.get("target_lang"),
    )
    data["source_lang"] = source_lang
    data["target_lang"] = target_lang
    experience_id = data.get("project_experience_id")
    if experience_id:
        experience = s.get(TranslatorProjectExperience, experience_id)
        if not experience or experience.translator_id != tid:
            raise HTTPException(400, "关联项目经历不属于该译员")
    return data


@router.get("/translators/{tid}/project-prices")
def list_project_prices(tid: int):
    with Session(engine) as s:
        get_translator(s, tid)
        rows = s.scalars(
            select(ProjectPrice)
            .where(ProjectPrice.translator_id == tid)
            .order_by(ProjectPrice.id.desc())
        ).all()
        return [row.as_dict() for row in rows]


@router.post("/translators/{tid}/project-prices")
def add_project_price(
    tid: int,
    body: ProjectPriceIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        data = _project_price_data(s, tid, body)
        row = ProjectPrice(translator_id=tid, **data)
        s.add(row)
        s.flush()
        audit(s, who, "新增", "项目专用价格", row.id, row.project_name)
        s.commit()
        s.refresh(row)
        return row.as_dict()


@router.put("/translators/{tid}/project-prices/{price_id}")
def update_project_price(
    tid: int,
    price_id: int,
    body: ProjectPriceIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        data = _project_price_data(s, tid, body)
        row = child_or_404(s, ProjectPrice, tid, price_id, "项目专用价格")
        for key, value in data.items():
            setattr(row, key, value)
        audit(s, who, "编辑", "项目专用价格", row.id, row.project_name)
        s.commit()
        s.refresh(row)
        return row.as_dict()


@router.delete("/translators/{tid}/project-prices/{price_id}")
def delete_project_price(
    tid: int,
    price_id: int,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = child_or_404(s, ProjectPrice, tid, price_id, "项目专用价格")
        audit(s, who, "删除", "项目专用价格", row.id, row.project_name)
        s.delete(row)
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


@router.delete("/translators/{tid}/complaints/{cid}")
def delete_complaint(tid: int, cid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        c = child_or_404(s, Complaint, tid, cid, "客诉")
        audit(s, who, "删除", "客诉", tid, f"{c.complaint_type or ''} {c.severity or ''}")
        s.delete(c)
        resync_translator(s, tid)
        s.commit()
        return {"ok": True}


# ---------------- 月度产能（项目字数自动分摊 + 按月人工修正）----------------
@router.get("/translators/{tid}/capacity")
def get_capacity(tid: int, month: str | None = None):
    with Session(engine) as s:
        translator = get_translator(s, tid)
        try:
            selected_month, _ = normalize_capacity_month(month)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        projects = s.scalars(
            select(TranslatorProjectExperience).where(
                TranslatorProjectExperience.translator_id == tid,
                TranslatorProjectExperience.project_status == "current",
            )
        ).all()
        override = s.scalar(
            select(CapacityMonthOverride).where(
                CapacityMonthOverride.translator_id == tid,
                CapacityMonthOverride.month == selected_month,
            )
        )
        return availability_snapshot(
            translator,
            projects,
            month=selected_month,
            override=override,
        )


@router.put("/translators/{tid}/capacity/override")
def upsert_capacity_override(
    tid: int,
    body: CapacityOverrideIn,
    month: str,
    w=Depends(require_writer),
):
    _, name = w
    with Session(engine) as s:
        translator = get_translator(s, tid)
        try:
            selected_month, _ = normalize_capacity_month(month)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        row = s.scalar(
            select(CapacityMonthOverride).where(
                CapacityMonthOverride.translator_id == tid,
                CapacityMonthOverride.month == selected_month,
            )
        )
        if row is None:
            row = CapacityMonthOverride(
                translator_id=tid,
                month=selected_month,
            )
            s.add(row)
        row.status = body.status
        row.reason = body.reason
        row.updated_by = name
        row.updated_at = datetime.now()
        audit(
            s,
            name,
            "人工修正",
            "月度产能",
            tid,
            f"{selected_month} {body.status}：{body.reason}",
        )
        s.commit()
        s.refresh(row)
        projects = s.scalars(
            select(TranslatorProjectExperience).where(
                TranslatorProjectExperience.translator_id == tid,
                TranslatorProjectExperience.project_status == "current",
            )
        ).all()
        return availability_snapshot(
            translator,
            projects,
            month=selected_month,
            override=row,
        )


@router.delete("/translators/{tid}/capacity/override")
def delete_capacity_override(
    tid: int,
    month: str,
    w=Depends(require_writer),
):
    _, name = w
    with Session(engine) as s:
        translator = get_translator(s, tid)
        try:
            selected_month, _ = normalize_capacity_month(month)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        row = s.scalar(
            select(CapacityMonthOverride).where(
                CapacityMonthOverride.translator_id == tid,
                CapacityMonthOverride.month == selected_month,
            )
        )
        if row:
            s.delete(row)
            audit(s, name, "清除人工修正", "月度产能", tid, selected_month)
        s.commit()
        projects = s.scalars(
            select(TranslatorProjectExperience).where(
                TranslatorProjectExperience.translator_id == tid,
                TranslatorProjectExperience.project_status == "current",
            )
        ).all()
        return availability_snapshot(translator, projects, month=selected_month)


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


@router.delete("/translators/{tid}/payment")
def delete_payment(tid: int, who: str = Depends(require_editor)):
    with Session(engine) as s:
        get_translator(s, tid)
        p = s.get(PaymentInfo, tid)
        if not p:
            raise HTTPException(404, "无支付信息")
        s.delete(p)
        audit(s, who, "删除", "支付信息", tid, "")
        s.commit()
        return {"ok": True}


# ---------------- 多支付账户 ----------------
def _payment_account_or_404(s: Session, tid: int, account_id: int):
    return child_or_404(s, PaymentAccount, tid, account_id, "支付账户")


def _validate_payment_account(data, existing: PaymentAccount | None = None):
    account_number = data.get("account_number") or (
        dec(existing.account_number_enc) if existing else None
    )
    tax_id = data.get("tax_id") or (
        dec(existing.tax_id_enc) if existing else None
    )
    values = [
        data.get("account_name"),
        account_number,
        data.get("bank_name"),
        data.get("bank_address"),
        data.get("swift_code"),
        data.get("routing_code"),
        tax_id,
        data.get("remarks"),
        existing.qr_stored_name if existing else None,
    ]
    if not any(value is not None and str(value).strip() for value in values):
        raise HTTPException(400, "支付方式至少填写一项账户信息")


def _apply_payment_account(row: PaymentAccount, data):
    for key in (
        "method", "currency", "account_name", "bank_name", "bank_address",
        "swift_code", "routing_code", "remarks",
    ):
        setattr(row, key, data.get(key))
    row.is_default = False
    if data.get("account_number"):
        row.account_number_enc = enc(data["account_number"])
    if data.get("tax_id"):
        row.tax_id_enc = enc(data["tax_id"])


@router.get("/translators/{tid}/payment-accounts")
def list_payment_accounts(tid: int):
    with Session(engine) as s:
        get_translator(s, tid)
        rows = s.scalars(
            select(PaymentAccount)
            .where(PaymentAccount.translator_id == tid)
            .order_by(PaymentAccount.id)
        ).all()
        return [row.as_dict() for row in rows]


@router.post("/translators/{tid}/payment-accounts")
def add_payment_account(
    tid: int,
    body: PaymentAccountIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        get_translator(s, tid)
        data = body.model_dump()
        _validate_payment_account(data)
        row = PaymentAccount(translator_id=tid, method=data["method"],
                             account_name=data["account_name"])
        _apply_payment_account(row, data)
        s.add(row)
        s.flush()
        audit(s, who, "新增", "支付账户", row.id, row.method)
        s.commit()
        s.refresh(row)
        return row.as_dict()


@router.put("/translators/{tid}/payment-accounts/{account_id}")
def update_payment_account(
    tid: int,
    account_id: int,
    body: PaymentAccountIn,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = _payment_account_or_404(s, tid, account_id)
        data = body.model_dump()
        _validate_payment_account(data, row)
        _apply_payment_account(row, data)
        audit(s, who, "编辑", "支付账户", row.id, row.method)
        s.commit()
        s.refresh(row)
        return row.as_dict()


@router.get("/translators/{tid}/payment-accounts/{account_id}/reveal")
def reveal_payment_account(
    tid: int,
    account_id: int,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = _payment_account_or_404(s, tid, account_id)
        audit(s, who, "查看明文", "支付账户", row.id, row.method)
        s.commit()
        return row.as_dict(reveal=True)


@router.post("/translators/{tid}/payment-accounts/{account_id}/qr")
async def upload_payment_qr(
    tid: int,
    account_id: int,
    file: UploadFile,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = _payment_account_or_404(s, tid, account_id)
        if row.method not in {"wechat", "alipay"}:
            raise HTTPException(400, "仅微信或支付宝账户支持收款码")
        saved = await save_upload(
            file, "payment_qr", allowed_extensions=IMAGE_EXTENSIONS,
        )
        old_name = row.qr_stored_name
        row.qr_stored_name = saved["stored_name"]
        row.qr_original_name = saved["original_name"]
        row.qr_mime = saved["mime_type"]
        audit(s, who, "上传", "收款码", row.id, saved["original_name"])
        s.commit()
        remove_stored(old_name)
        return row.as_dict()


@router.get("/translators/{tid}/payment-accounts/{account_id}/qr")
def download_payment_qr(
    tid: int,
    account_id: int,
    _viewer=Depends(require_authenticated),
):
    with Session(engine) as s:
        row = _payment_account_or_404(s, tid, account_id)
        if not row.qr_stored_name:
            raise HTTPException(404, "无收款码")
        return FileResponse(
            stored_path(row.qr_stored_name),
            media_type=row.qr_mime,
            filename=row.qr_original_name,
        )


@router.delete("/translators/{tid}/payment-accounts/{account_id}")
def delete_payment_account(
    tid: int,
    account_id: int,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = _payment_account_or_404(s, tid, account_id)
        qr_name = row.qr_stored_name
        audit(s, who, "删除", "支付账户", row.id, row.method)
        s.delete(row)
        s.commit()
        remove_stored(qr_name)
        return {"ok": True}


# ---------------- 资质附件 ----------------
ATTACHMENT_CATEGORIES = {"certificate", "test", "sample", "other"}


@router.get("/translators/{tid}/attachments")
def list_attachments(
    tid: int,
    _viewer=Depends(require_authenticated),
):
    with Session(engine) as s:
        get_translator(s, tid)
        rows = s.scalars(
            select(TranslatorAttachment)
            .where(TranslatorAttachment.translator_id == tid)
            .order_by(TranslatorAttachment.id.desc())
        ).all()
        return [row.as_dict() for row in rows]


@router.post("/translators/{tid}/attachments")
async def upload_attachment(
    tid: int,
    file: UploadFile,
    category: str = Form(...),
    who: str = Depends(require_editor),
):
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(400, "附件分类非法")
    with Session(engine) as s:
        get_translator(s, tid)
        saved = await save_upload(file, "qualifications")
        row = TranslatorAttachment(
            translator_id=tid,
            category=category,
            original_name=saved["original_name"],
            stored_name=saved["stored_name"],
            mime_type=saved["mime_type"],
            size_bytes=saved["size_bytes"],
            sha256=saved["sha256"],
        )
        s.add(row)
        s.flush()
        audit(s, who, "上传", "资质附件", row.id, row.original_name)
        s.commit()
        s.refresh(row)
        return row.as_dict()


@router.get("/translators/{tid}/attachments/{attachment_id}")
def download_attachment(
    tid: int,
    attachment_id: int,
    _viewer=Depends(require_authenticated),
):
    with Session(engine) as s:
        row = child_or_404(
            s, TranslatorAttachment, tid, attachment_id, "资质附件",
        )
        return FileResponse(
            stored_path(row.stored_name),
            media_type=row.mime_type,
            filename=row.original_name,
        )


@router.delete("/translators/{tid}/attachments/{attachment_id}")
def delete_attachment(
    tid: int,
    attachment_id: int,
    who: str = Depends(require_editor),
):
    with Session(engine) as s:
        row = child_or_404(
            s, TranslatorAttachment, tid, attachment_id, "资质附件",
        )
        stored_name = row.stored_name
        audit(s, who, "删除", "资质附件", row.id, row.original_name)
        s.delete(row)
        s.commit()
        remove_stored(stored_name)
        return {"ok": True}
