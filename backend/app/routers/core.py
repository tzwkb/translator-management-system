"""鉴权与总览接口。"""
from datetime import date, timedelta

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import engine
from ..models import Translator
from ..schemas import LoginIn
from ..security import USERS, _tok, make_token, parse_token

router = APIRouter(prefix="/api")


@router.post("/login")
def login(body: LoginIn):
    if body.user not in USERS:
        raise HTTPException(404, "用户不存在")
    role, name = USERS[body.user]
    return {"token": make_token(role, name), "role": role, "name": name}


@router.get("/me")
def me(authorization: str = Header(None)):
    role, name = parse_token(_tok(authorization))
    return {"role": role, "name": name}


@router.get("/overview")
def overview():
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=30)).isoformat()
    with Session(engine) as s:
        rows = s.scalars(select(Translator).where(Translator.deleted_at.is_(None))).all()
        by, expiring = {}, 0
        for t in rows:
            by[t.status] = by.get(t.status, 0) + 1
            if t.contract_expiry and today <= t.contract_expiry <= soon:
                expiring += 1
        return {"total": len(rows), "active": by.get("Active", 0), "dormant": by.get("Dormant", 0),
                "blacklisted": by.get("Blacklisted", 0), "probation": by.get("Probation", 0),
                "expiring_30d": expiring}
