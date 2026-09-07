from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import FRONTEND_DIR
from ..db import engine
from ..services import LANGUAGE_OPTIONS
from . import service
from .schemas import IntakeIn

router = APIRouter()


@router.get("/intake", include_in_schema=False)
def intake_page():
    return FileResponse(FRONTEND_DIR / "intake.html")


@router.get("/intake-assets/{asset}", include_in_schema=False)
def intake_asset(asset: str):
    if asset not in {"public.js", "public.css"}:
        raise HTTPException(404)
    return FileResponse(FRONTEND_DIR / "intake" / asset)


@router.get("/api/public/intake")
def invitation_context(authorization: str | None = Header(None)):
    with Session(engine) as session:
        invite = service.resolve_invite(session, authorization)
        row = service.get_submission(session, invite.id)
        result = {"email": invite.email, "expires_at": service.iso(invite.expires_at),
                  "is_update": bool(invite.translator_id), "languages": LANGUAGE_OPTIONS,
                  "submission": service.receipt(row) if row else None}
        if row and row.status == "needs_info":
            result["draft"] = IntakeIn.model_validate_json(row.payload).model_dump(exclude_none=True)
        return result


@router.post("/api/public/intake")
def submit_intake(body: IntakeIn, authorization: str | None = Header(None)):
    with Session(engine) as session, session.begin():
        invite = service.resolve_invite(session, authorization, lock=True)
        return service.submit(session, invite, body)
