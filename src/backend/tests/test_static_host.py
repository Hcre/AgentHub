"""M4①.1 静态托管 + 路径穿越防御测试（infrastructure/deploy/static_host）。

两套：
A. 路径穿越（M4）：write_files 拒绝绝对路径 / .. 越权 / 空键；_safe_id 拒非法 id。
B. 静态托管（M4）：write_files 真落盘；build_preview_url 返真 /preview/{id}/；
   make_zip 真打 zip；remove 清理。
"""

from __future__ import annotations

import base64
import os
import zipfile
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")

import pytest

from app.infrastructure.deploy import static_host

# ============ A. 路径穿越（M4）============


def test_write_files_rejects_parent_traversal() -> None:
    """.. 越权键被拒，且不在磁盘留下越权文件。"""
    dep_id = uuid4()
    try:
        with pytest.raises(ValueError):
            static_host.write_files(dep_id, {"../evil.txt": "x"})
    finally:
        static_host.remove(dep_id)


def test_write_files_rejects_absolute_path() -> None:
    dep_id = uuid4()
    try:
        with pytest.raises(ValueError):
            static_host.write_files(dep_id, {"/etc/passwd": "x"})
    finally:
        static_host.remove(dep_id)


def test_write_files_rejects_empty_key() -> None:
    dep_id = uuid4()
    try:
        with pytest.raises(ValueError):
            static_host.write_files(dep_id, {"": "x"})
    finally:
        static_host.remove(dep_id)


def test_safe_id_rejects_illegal_chars() -> None:
    """_safe_id 拒绝含路径分隔/特殊字符的 id（防御性）。"""
    with pytest.raises(ValueError):
        static_host._safe_id("../../etc")


# ============ B. 静态托管（M4）============


def test_write_files_persists_and_stays_in_base() -> None:
    """正常落盘：文件真写入 _assets/deploy/{id}/，含嵌套子目录，内容一致。"""
    dep_id = uuid4()
    try:
        base = static_host.write_files(
            dep_id,
            {"index.html": "<h1>hi</h1>", "assets/app.js": "console.log(1)"},
        )
        assert base.is_dir()
        idx = base / "index.html"
        nested = base / "assets" / "app.js"
        assert idx.read_text(encoding="utf-8") == "<h1>hi</h1>"
        assert nested.read_text(encoding="utf-8") == "console.log(1)"
        # 落盘目录确实在 base 之下（无穿越）
        assert str(nested.resolve()).startswith(str(base.resolve()))
    finally:
        static_host.remove(dep_id)


def test_build_preview_url_is_real_preview_path() -> None:
    """预览地址是真 /preview/{id}/ 路径，非旧假域名。"""
    dep_id = uuid4()
    url = static_host.build_preview_url(dep_id, host="http://127.0.0.1:8000")
    assert url == f"http://127.0.0.1:8000/preview/{dep_id}/"
    assert "agenthub-deploy.com" not in url


def test_make_zip_creates_real_archive() -> None:
    """package 类型真打 zip，zip 内含落盘文件。"""
    dep_id = uuid4()
    try:
        zip_path = static_host.make_zip(
            dep_id, {"index.html": "x", "a.js": "y"}
        )
        assert Path(zip_path).is_file()
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
        assert "index.html" in names
        assert "a.js" in names
    finally:
        static_host.remove(dep_id)


def test_remove_clears_deploy_dir() -> None:
    dep_id = uuid4()
    base = static_host.write_files(dep_id, {"index.html": "x"})
    assert base.is_dir()
    static_host.remove(dep_id)
    assert not base.exists()
