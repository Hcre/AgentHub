"""附件上传/下载路由端到端测试（httpx AsyncClient + TestClient multipart）。

覆盖：
  1) 上传小 txt → 200 + 返回 id/url
  2) GET /api/attachments/{id} 拿到原内容 + Content-Disposition
  3) 不允许的 MIME → 415
  4) 不存在的 id → 404
"""

from __future__ import annotations

import io
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routers import attachments as attachments_module


@pytest.fixture
def isolated_storage(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """每个测试用例用一个独立 tmp 目录，避免污染源 storage。"""
    tmp = Path(tempfile.mkdtemp(prefix="attachments-test-"))
    monkeypatch.setattr(attachments_module, "STORAGE_DIR", tmp)
    monkeypatch.setattr(attachments_module, "META_FILE", tmp / "_meta.json")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _client() -> TestClient:
    return TestClient(app)


def test_upload_then_get_roundtrip(isolated_storage: Path) -> None:
    """上传 txt → 通过返回的 url 再 GET → 内容字节完全一致。"""
    payload = b"hello attachments, this is a test fixture.\n"
    with _client() as c:
        resp = c.post(
            "/api/attachments/multipart",
            files={"file": ("hello.txt", io.BytesIO(payload), "text/plain")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "hello.txt"
    assert body["size"] == len(payload)
    assert body["mime"] == "text/plain"
    assert body["url"] == f"/api/attachments/{body['id']}"
    assert len(body["id"]) == 32  # uuid4 hex

    with _client() as c:
        got = c.get(body["url"])
    assert got.status_code == 200
    assert got.content == payload
    # Content-Disposition 携带原文件名（RFC 5987 形式，浏览器能识别）
    cd = got.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "hello.txt" in cd

    # 落盘 + meta 都写到了 isolated_storage
    on_disk_files = list(isolated_storage.glob("*"))
    assert any(p.suffix == ".txt" for p in on_disk_files)
    assert (isolated_storage / "_meta.json").is_file()


def test_upload_unsupported_mime_returns_415(isolated_storage: Path) -> None:
    payload = b"\x00\x01\x02 binary blob"
    with _client() as c:
        resp = c.post(
            "/api/attachments/multipart",
            files={"file": ("blob.bin", io.BytesIO(payload), "application/octet-stream")},
        )
    assert resp.status_code == 415


def test_get_unknown_id_returns_404(isolated_storage: Path) -> None:
    with _client() as c:
        resp = c.get("/api/attachments/00000000000000000000000000000000")
    assert resp.status_code == 404


def test_upload_empty_file_returns_422(isolated_storage: Path) -> None:
    with _client() as c:
        resp = c.post(
            "/api/attachments/multipart",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )
    assert resp.status_code == 422


def test_upload_oversize_file_returns_413(isolated_storage: Path) -> None:
    # 11 MiB > 10 MiB 限制
    big = b"x" * (11 * 1024 * 1024)
    with _client() as c:
        resp = c.post(
            "/api/attachments/multipart",
            files={"file": ("big.txt", io.BytesIO(big), "text/plain")},
        )
    assert resp.status_code == 413
