"""文件附件路由（/api/attachments/*）。

MVP 范围：multipart 上传 + 浏览器下载。10MB 硬限，白名单 MIME。
元数据持久化到 sidecar JSON（_meta.json），重启后保留。
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

# 限制：10 MiB = 10 * 1024 * 1024 bytes
MAX_FILE_SIZE = 10 * 1024 * 1024

# 白名单 MIME 类型（任务约束）
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "application/pdf",
        "text/markdown",
        "text/plain",
        "application/zip",
    }
)

# MIME → 文件扩展名（覆盖白名单范围内所有允许类型）
MIME_TO_EXT: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "application/pdf": "pdf",
    "text/markdown": "md",
    "text/plain": "txt",
    "application/zip": "zip",
}

# 路径：src/backend/app/api/routers/attachments.py → parents[3] = src/backend/
STORAGE_DIR: Path = Path(__file__).resolve().parents[3] / "storage" / "attachments"
META_FILE: Path = STORAGE_DIR / "_meta.json"

# 写锁（同一进程内串行化 _meta.json 读写）
_meta_lock = asyncio.Lock()


def _sanitize_filename(name: str) -> str:
    """清理文件名，仅保留安全字符；空则返回 'download'。"""
    if not name:
        return "download"
    # 去路径分隔符（\ /）+ 控制字符（ASCII < 0x20）
    cleaned = re.sub(r"[\\/]", "_", name)
    cleaned = re.sub(r"[\x00-\x1f]", "_", cleaned).strip()
    return cleaned or "download"


def _load_meta() -> dict[str, dict[str, Any]]:
    """读 _meta.json；不存在或损坏则返空 dict。"""
    if not META_FILE.exists():
        return {}
    try:
        data = json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


async def _save_meta(meta: dict[str, dict[str, Any]]) -> None:
    """原子写 _meta.json（tmp + replace）。"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = META_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(META_FILE)


def _guess_ext(filename: str | None, content_type: str) -> str:
    """优先用白名单 MIME 决定 ext；fallback 到 mimetypes 猜测。"""
    if content_type in MIME_TO_EXT:
        return MIME_TO_EXT[content_type]
    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed and guessed in MIME_TO_EXT:
        return MIME_TO_EXT[guessed]
    # 最后 fallback：原文件后缀或 'bin'
    if filename:
        suffix = Path(filename).suffix.lstrip(".").lower()
        if suffix and re.fullmatch(r"[a-z0-9]{1,8}", suffix):
            return suffix
    return "bin"


router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("/multipart")
async def upload_multipart(file: UploadFile = File(...)) -> dict[str, Any]:
    """上传附件：返回 { id, name, size, mime, url }。"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}",
        )

    # 流式读取，超 10MB 立即中断
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {MAX_FILE_SIZE} bytes limit",
            )
        chunks.append(chunk)
    await file.close()

    if total == 0:
        raise HTTPException(status_code=422, detail="Empty file")

    # 落盘
    file_id = uuid.uuid4().hex
    ext = _guess_ext(file.filename, content_type)
    on_disk = STORAGE_DIR / f"{file_id}.{ext}"
    on_disk.write_bytes(b"".join(chunks))

    # 写元数据
    safe_name = _sanitize_filename(file.filename or "download")
    async with _meta_lock:
        meta = _load_meta()
        meta[file_id] = {
            "name": safe_name,
            "size": total,
            "mime": content_type,
            "ext": ext,
            "path": on_disk.name,
        }
        await _save_meta(meta)

    return {
        "id": file_id,
        "name": safe_name,
        "size": total,
        "mime": content_type,
        "url": f"/api/attachments/{file_id}",
    }


@router.get("/{file_id}")
async def get_attachment(file_id: str) -> FileResponse:
    """下载/打开附件。"""
    if not re.fullmatch(r"[0-9a-f]{32}", file_id):
        raise HTTPException(status_code=404, detail="Attachment not found")

    meta = _load_meta()
    entry = meta.get(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Attachment not found")

    on_disk = STORAGE_DIR / entry["path"]
    if not on_disk.is_file():
        raise HTTPException(status_code=404, detail="Attachment file missing")

    return FileResponse(
        path=on_disk,
        media_type=entry.get("mime") or "application/octet-stream",
        filename=entry.get("name") or on_disk.name,
    )
