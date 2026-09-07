import hashlib
import json
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update

from ..models import (LanguagePair, Translator, TranslatorIntakeInvite,
                      TranslatorIntakeSubmission, TranslatorProjectExperience)
from ..services import (audit, get_or_create_language_pair, get_translator,
                        resync_translator, svc_add_project_experience)
from ..translator_identity import (add_translator_alias, assert_name_not_reserved,
                                   exact_translator_ids_for_name)
from .schemas import PROFILE_FIELDS, RATE_FIELDS, IntakeIn


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.isoformat(timespec="seconds") + "Z" if value else None


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lock_invite(session, invite_id):
    # 所有提交、撤销、审核先取得同一邀请的写锁，避免重复处理及撤销竞态。
    changed = session.execute(update(TranslatorIntakeInvite).where(
        TranslatorIntakeInvite.id == invite_id,
    ).values(revision=TranslatorIntakeInvite.revision + 1)).rowcount
    if not changed:
        raise HTTPException(404, "邀请不存在")
    return session.get(TranslatorIntakeInvite, invite_id, populate_existing=True)


def resolve_invite(session, authorization, *, lock=False):
    token = (authorization or "").removeprefix("Invite ")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(404, "链接无效，请联系资源负责人 / Invalid link; contact your coordinator")
    token_hash = digest(token)
    if lock:
        changed = session.execute(update(TranslatorIntakeInvite).where(
            TranslatorIntakeInvite.token_hash == token_hash,
        ).values(revision=TranslatorIntakeInvite.revision + 1)).rowcount
        if not changed:
            raise HTTPException(404, "链接无效 / Invalid link")
    invite = session.scalar(select(TranslatorIntakeInvite).where(TranslatorIntakeInvite.token_hash == token_hash))
    if not invite:
        raise HTTPException(404, "链接无效 / Invalid link")
    if invite.revoked_at or invite.expires_at <= now():
        raise HTTPException(410, "链接已过期或撤销，请联系资源负责人获取新链接 / Link expired or revoked; request a new link")
    return invite


def get_submission(session, invite_id):
    return session.scalar(select(TranslatorIntakeSubmission).where(TranslatorIntakeSubmission.invite_id == invite_id))


def receipt(submission):
    return {
        "id": submission.id, "status": submission.status, "version": submission.version,
        "submitted_at": iso(submission.submitted_at), "review_note": submission.review_note,
    }


def submit(session, invite, data: IntakeIn):
    if data.email != invite.email:
        raise HTTPException(400, "请使用邀请邮箱 / Use the invited email address")
    payload = canonical(data.model_dump(exclude_none=True))
    row = get_submission(session, invite.id)
    if row and row.status != "needs_info":
        if row.payload == payload:
            return receipt(row)
        raise HTTPException(409, "资料已提交，需修改请联系资源负责人退回补充 / Already submitted; ask your coordinator to reopen it")
    if row:
        row.payload = payload
        row.version += 1
        row.submitted_at = now()
        row.status = "pending"
        row.review_note = None
        row.reviewed_at = None
        row.reviewed_by = None
    else:
        row = TranslatorIntakeSubmission(invite_id=invite.id, status="pending", version=1,
                                         payload=payload, submitted_at=now())
        session.add(row)
    session.flush()
    audit(session, "译员自填", "提交", "资料申请", row.id, f"邀请 #{invite.id}，版本 {row.version}")
    return receipt(row)


def candidate_translators(session, payload):
    ids = exact_translator_ids_for_name(session, payload["name"])
    rows = session.scalars(select(Translator).where(
        Translator.deleted_at.is_(None),
        (func.lower(func.trim(Translator.email)) == payload["email"]) | Translator.id.in_(ids),
    ).order_by(Translator.id)).all()
    return [{"id": row.id, "name": row.name, "email": row.email} for row in rows]


def resolve_target(session, invite, payload, target_id):
    candidates = candidate_translators(session, payload)
    if invite.translator_id:
        if target_id and target_id != invite.translator_id:
            raise HTTPException(409, "邀请已绑定译员，不能改为其他记录")
        return invite.translator_id, candidates
    if target_id and target_id not in {row["id"] for row in candidates}:
        raise HTTPException(409, "仅能合并到同名或同邮箱候选记录")
    return target_id, candidates


def profile_snapshot(session, target_id):
    if not target_id:
        return None, None
    translator = get_translator(session, target_id)
    profile = translator.as_dict()
    profile["language_pairs"] = [row.as_dict() for row in session.scalars(select(LanguagePair).where(
        LanguagePair.translator_id == target_id,
    ).order_by(LanguagePair.id))]
    profile["projects"] = [row.as_dict() for row in session.scalars(select(TranslatorProjectExperience).where(
        TranslatorProjectExperience.translator_id == target_id,
    ).order_by(TranslatorProjectExperience.id))]
    return profile, digest(canonical(profile))


def apply_profile(session, data, target_id, request, who):
    conflicts = {row["id"] for row in candidate_translators(session, data)} - {target_id}
    if conflicts:
        raise HTTPException(409, "存在同名或同邮箱记录，请先选择合并目标或处理冲突")
    assert_name_not_reserved(session, data["name"], target_id)
    values = {key: data[key] for key in PROFILE_FIELDS if data.get(key) is not None}
    if target_id:
        translator = get_translator(session, target_id)
        old_name = translator.name
        for key, value in values.items():
            setattr(translator, key, value)
        if old_name != translator.name:
            add_translator_alias(session, translator.id, old_name)
    else:
        if not request.onboarding_date:
            raise HTTPException(400, "新译员请确认入库日期")
        translator = Translator(**values, onboarding_date=request.onboarding_date,
                                status=request.status, settlement_mode=request.settlement_mode,
                                source="译员自填链接")
        session.add(translator)
        session.flush()
    for pair in data["language_pairs"]:
        row = get_or_create_language_pair(session, translator.id, pair["source_lang"], pair["target_lang"])
        if request.include_rates and any(pair.get(key) is not None for key in RATE_FIELDS):
            currency = pair["currency"]
            if row.currency and row.currency != currency and any(
                getattr(row, key) is not None and pair.get(key) is None for key in RATE_FIELDS
            ):
                raise HTTPException(409, "报价币种改变时须补齐已有费率，或取消本次写入报价")
            for key in RATE_FIELDS:
                if pair.get(key) is not None:
                    setattr(row, key, pair[key])
            row.currency = currency
            row.rate_confirmed_date = now().date().isoformat()
    projects = session.scalars(select(TranslatorProjectExperience).where(
        TranslatorProjectExperience.translator_id == translator.id,
    )).all()
    def project_key(value):
        return canonical({key: item for key, item in value.items() if key not in {"id", "translator_id"} and item is not None})
    existing = {project_key(row.as_dict()) for row in projects}
    for project in data.get("projects", []):
        key = project_key(project)
        if key not in existing:
            svc_add_project_experience(session, translator.id, project, who)
            existing.add(key)
    session.flush()
    resync_translator(session, translator.id)
    return translator.id


def review(session, submission_id, request, who):
    invite_id = session.scalar(select(TranslatorIntakeSubmission.invite_id).where(TranslatorIntakeSubmission.id == submission_id))
    if not invite_id:
        raise HTTPException(404, "资料申请不存在")
    invite = lock_invite(session, invite_id)
    row = session.get(TranslatorIntakeSubmission, submission_id, populate_existing=True)
    if row.version != request.version:
        raise HTTPException(409, "译员已重新提交，请刷新后重新审核")
    result_status = {"approve": "approved", "reject": "rejected", "needs_info": "needs_info"}[request.action]
    if row.status == result_status:
        return {**receipt(row), "translator_id": row.translator_id}
    if row.status not in {"pending", "needs_info"}:
        raise HTTPException(409, "该申请已经处理")
    if request.action == "approve":
        if invite.revoked_at:
            raise HTTPException(409, "邀请已撤销，不能入库")
        if row.status != "pending":
            raise HTTPException(409, "请等待译员补充后重新提交")
        payload = IntakeIn.model_validate_json(row.payload).model_dump(exclude_none=True)
        target_id, _ = resolve_target(session, invite, payload, request.target_id)
        _, fingerprint = profile_snapshot(session, target_id)
        if fingerprint != request.profile_fingerprint:
            raise HTTPException(409, "原档案已变更，请刷新差异后重新审核")
        try:
            row.translator_id = apply_profile(session, payload, target_id, request, who)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    row.status = result_status
    row.review_note = request.note
    row.reviewed_by = who
    row.reviewed_at = now()
    audit(session, who, "审核", "资料申请", row.id,
          f"{row.status}，版本 {row.version}，译员 #{row.translator_id or '-'}，确认报价：{request.include_rates}")
    session.flush()
    return {**receipt(row), "translator_id": row.translator_id}
