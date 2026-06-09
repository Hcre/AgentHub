"""M3-B pptx 抽页三路径 + M3-C 版本历史非 git 降级测试（api/routers/skills FS 端点）。

直接调用端点协程（避开 DB/鉴权），断言 HTTPException 状态码与降级返回。

两套：
A. pptx 三路径（M3-B）：400 空 path / 404 文件不存在 / 415 非 pptx。
   （501 缺 python-pptx 不在本机稳定复现，留 live 验证。）
B. 非 git 降级（M3-C）：file-history 对非 git 仓库文件返 is_git=False + 空列表；
   file-at-rev 对非 git 仓库文件返 404。
"""

from __future__ import annotations

import base64
import os
import tempfile

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")

import pytest
from fastapi import HTTPException

from app.api.routers.skills import (
    FileAtRevRequest,
    FileHistoryRequest,
    PptxSlidesRequest,
    fs_file_at_rev,
    fs_file_history,
    fs_pptx_slides,
)

# ============ A. pptx 三路径（M3-B）============


@pytest.mark.asyncio
async def test_pptx_empty_path_400() -> None:
    with pytest.raises(HTTPException) as exc:
        await fs_pptx_slides(PptxSlidesRequest(path=""))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_pptx_missing_file_404() -> None:
    with pytest.raises(HTTPException) as exc:
        await fs_pptx_slides(
            PptxSlidesRequest(path=os.path.join(tempfile.gettempdir(), "no-such-deck.pptx"))
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_pptx_non_pptx_file_415() -> None:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("not a pptx")
        path = f.name
    try:
        with pytest.raises(HTTPException) as exc:
            await fs_pptx_slides(PptxSlidesRequest(path=path))
        assert exc.value.status_code == 415
    finally:
        os.unlink(path)


# ============ B. 非 git 降级（M3-C）============


@pytest.mark.asyncio
async def test_file_history_non_git_returns_empty() -> None:
    """非 git 仓库内的文件 → is_git=False + commits=[]（不报错，前端显示空态）。"""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("plain file outside git")
        path = f.name
    try:
        result = await fs_file_history(FileHistoryRequest(path=path))
        assert result["is_git"] is False
        assert result["commits"] == []
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_file_history_missing_file_404() -> None:
    with pytest.raises(HTTPException) as exc:
        await fs_file_history(
            FileHistoryRequest(path=os.path.join(tempfile.gettempdir(), "no-such-file.txt"))
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_file_at_rev_non_git_404() -> None:
    """非 git 仓库文件取某版本 → 404（该版本无此文件 / sha 无效）。"""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("plain")
        path = f.name
    try:
        with pytest.raises(HTTPException) as exc:
            await fs_file_at_rev(FileAtRevRequest(path=path, rev="deadbeef"))
        assert exc.value.status_code == 404
    finally:
        os.unlink(path)
