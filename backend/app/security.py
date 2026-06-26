"""字段级加密（AES-256-GCM）+ 鉴权（按角色签名 token）+ 权限依赖。"""
import base64
import hashlib
import hmac
import os
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Header, HTTPException

from . import config

# ---------------- 字段级加密 ----------------
if config.AES_KEY_HEX:
    KEY = bytes.fromhex(config.AES_KEY_HEX)
elif config.KEYFILE.exists():
    KEY = config.KEYFILE.read_bytes()
else:
    KEY = AESGCM.generate_key(bit_length=256)
    config.KEYFILE.write_bytes(KEY)
_aes = AESGCM(KEY)


def enc(text):
    if not text:
        return None
    nonce = os.urandom(12)
    return nonce + _aes.encrypt(nonce, str(text).encode(), None)


def dec(blob):
    if not blob:
        return None
    return _aes.decrypt(blob[:12], blob[12:], None).decode()


def mask(text):
    if not text:
        return None
    t = str(text)
    return ("*" * max(0, len(t) - 4)) + t[-4:] if len(t) > 4 else "****"


# ---------------- 鉴权（首版免密码，token 按角色签名）----------------
AUTH_SECRET = config.JWT_SECRET or os.urandom(16).hex()
USERS = {"资源端": ("editor", "资源端"), "财务": ("editor", "财务"), "boss": ("viewer", "boss"),
         "资源端Agent": ("agent", "资源端Agent")}


def make_token(role, name):
    exp = int(time.time()) + config.TOKEN_TTL
    payload = f"{role}|{name}|{exp}"
    sig = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode()


def parse_token(tok):
    if not tok:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(tok.encode()).decode()
    except Exception:
        return None, None
    if "." not in raw:
        return None, None
    payload, sig = raw.rsplit(".", 1)
    good = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, good):
        return None, None
    parts = payload.split("|")
    if len(parts) != 3:
        return None, None
    role, name, exp = parts
    if int(exp) < time.time():
        return None, None
    return role, name


def _tok(authorization):
    if not authorization:
        return None
    return authorization.split(" ", 1)[1] if " " in authorization else authorization


def require_editor(authorization: str = Header(None)):
    role, name = parse_token(_tok(authorization))
    if role != "editor":
        raise HTTPException(403, "只读视角无编辑权限")
    return name


def require_writer(authorization: str = Header(None)):
    role, name = parse_token(_tok(authorization))
    if role not in ("editor", "agent"):
        raise HTTPException(403, "无编辑权限")
    return role, name
