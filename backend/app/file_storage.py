"""受控本地文件存储。"""
import hashlib
import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import UPLOAD_DIR, UPLOAD_MAX_BYTES

DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".png", ".jpg", ".jpeg",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _valid_signature(extension: str, data: bytes) -> bool:
    if extension == ".pdf":
        return data.startswith(b"%PDF-")
    if extension == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if extension in {".docx", ".xlsx"}:
        return data.startswith(b"PK\x03\x04")
    if extension in {".doc", ".xls"}:
        return data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension == ".txt":
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return False


async def save_upload(
    upload: UploadFile,
    namespace: str,
    allowed_extensions: set[str] | None = None,
) -> dict:
    original_name = Path(upload.filename or "").name
    extension = Path(original_name).suffix.lower()
    allowed = allowed_extensions or DOCUMENT_EXTENSIONS
    if not original_name or extension not in allowed:
        raise HTTPException(400, "文件类型不允许")
    data = await upload.read(UPLOAD_MAX_BYTES + 1)
    if not data:
        raise HTTPException(400, "文件为空")
    if len(data) > UPLOAD_MAX_BYTES:
        raise HTTPException(400, f"单文件不能超过 {UPLOAD_MAX_BYTES // 1024 // 1024} MB")
    if not _valid_signature(extension, data):
        raise HTTPException(400, "文件内容与扩展名不匹配")
    target_dir = (UPLOAD_DIR / namespace).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    path = (target_dir / stored_name).resolve()
    if path.parent != target_dir:
        raise HTTPException(400, "文件名非法")
    path.write_bytes(data)
    return {
        "original_name": original_name,
        "stored_name": f"{namespace}/{stored_name}",
        "mime_type": MIME_BY_EXTENSION.get(
            extension,
            upload.content_type or mimetypes.guess_type(original_name)[0]
            or "application/octet-stream",
        ),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def stored_path(stored_name: str) -> Path:
    root = UPLOAD_DIR.resolve()
    path = (root / stored_name).resolve()
    if path == root or root not in path.parents or not path.is_file():
        raise HTTPException(404, "文件不存在")
    return path


def remove_stored(stored_name: str | None):
    if not stored_name:
        return
    try:
        stored_path(stored_name).unlink()
    except HTTPException:
        return
