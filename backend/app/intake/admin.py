import json
import os
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import TranslatorIntakeInvite, TranslatorIntakeSubmission
from ..security import require_editor
from ..services import audit, get_translator
from . import service
from .schemas import InviteIn, ReviewIn

router = APIRouter(prefix="/api/intake", dependencies=[Depends(require_editor)])


def private_response(response: Response):
    response.headers["Cache-Control"] = "no-store"


router.dependencies.append(Depends(private_response))


@router.post("/invites")
def create_invite(body: InviteIn, request: Request, who=Depends(require_editor)):
    base = os.getenv("INTAKE_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        parsed = urlsplit(base)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (
            parsed.scheme != "https" and not (local and parsed.scheme == "http")
        ):
            raise HTTPException(503, "INTAKE_PUBLIC_BASE_URL 应为 HTTPS 站点地址（本机预览可用 HTTP）")
    token = secrets.token_urlsafe(32)
    with Session(engine) as session, session.begin():
        if body.translator_id:
            get_translator(session, body.translator_id)
        row = TranslatorIntakeInvite(email=body.email, translator_id=body.translator_id,
                                      token_hash=service.digest(token), created_by=who,
                                      created_at=service.now(), expires_at=service.now() + timedelta(days=body.expires_days))
        session.add(row)
        session.flush()
        audit(session, who, "创建", "资料邀请", row.id, f"邮箱 {row.email}，绑定译员 #{row.translator_id or '-'}")
        return {"id": row.id, "url": f"{base or str(request.base_url).rstrip('/')}/intake#{token}",
                "expires_at": service.iso(row.expires_at), "preview_only": not bool(base) or local}


@router.get("/invites")
def list_invites(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    with Session(engine) as session:
        rows = session.execute(select(TranslatorIntakeInvite, TranslatorIntakeSubmission).outerjoin(
            TranslatorIntakeSubmission, TranslatorIntakeSubmission.invite_id == TranslatorIntakeInvite.id,
        ).order_by(TranslatorIntakeInvite.id.desc()).offset(offset).limit(limit)).all()
        return [{"id": invite.id, "email": invite.email, "translator_id": invite.translator_id,
                 "created_by": invite.created_by, "created_at": service.iso(invite.created_at),
                 "expires_at": service.iso(invite.expires_at), "revoked_at": service.iso(invite.revoked_at),
                 "expired": invite.expires_at <= service.now(), "submission_id": submission.id if submission else None,
                 "status": submission.status if submission else "unsubmitted"} for invite, submission in rows]


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(invite_id: int, who=Depends(require_editor)):
    with Session(engine) as session, session.begin():
        invite = service.lock_invite(session, invite_id)
        if not invite.revoked_at:
            invite.revoked_at = service.now()
            audit(session, who, "撤销", "资料邀请", invite.id)
        return {"id": invite.id, "revoked_at": service.iso(invite.revoked_at)}


@router.get("/submissions")
def list_submissions(status: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    with Session(engine) as session:
        query = select(TranslatorIntakeSubmission).order_by(TranslatorIntakeSubmission.id.desc())
        if status:
            query = query.where(TranslatorIntakeSubmission.status == status)
        rows = session.scalars(query.offset(offset).limit(limit)).all()
        return [{**service.receipt(row), "name": json.loads(row.payload)["name"],
                 "email": json.loads(row.payload)["email"], "translator_id": row.translator_id} for row in rows]


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: int, target_id: int | None = Query(None, gt=0)):
    with Session(engine) as session:
        row = session.get(TranslatorIntakeSubmission, submission_id)
        if not row:
            raise HTTPException(404, "资料申请不存在")
        invite = session.get(TranslatorIntakeInvite, row.invite_id)
        payload = json.loads(row.payload)
        if row.status == "approved":
            target_id, candidates = row.translator_id, []
        else:
            target_id, candidates = service.resolve_target(session, invite, payload, target_id)
        profile, fingerprint = service.profile_snapshot(session, target_id)
        return {**service.receipt(row), "payload": payload, "current": profile,
                "profile_fingerprint": fingerprint, "target_id": target_id,
                "bound_translator_id": invite.translator_id, "candidates": candidates,
                "revoked": bool(invite.revoked_at), "reviewed_by": row.reviewed_by,
                "reviewed_at": service.iso(row.reviewed_at)}


@router.post("/submissions/{submission_id}/review")
def review_submission(submission_id: int, body: ReviewIn, who=Depends(require_editor)):
    with Session(engine) as session, session.begin():
        return service.review(session, submission_id, body, who)
