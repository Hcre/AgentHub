"""P1-3 CLI PATH 扫描器测试（spec 04-commands §6.7 B-5.4-P1-3）。

3 路径：
1. found — bin 在 PATH 里 → available=True, path 非空
2. not found — bin 不在 PATH → available=False, error 信息
3. multi-match — 多个 bin 一次扫 → 顺序与输入一致
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

os.environ.setdefault("SECRET_KEY", base64.b64encode(b"0" * 32).decode("ascii"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_ADAPTER_MODE", "mock")
os.environ.setdefault("ENV", "test")

import pytest

from app.infrastructure.cli_scanner import (
    CliScanResult,
    scan_all,
    scan_one,
)


@pytest.fixture
def fake_bin_in_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """建一个假 bin 文件 + 加到 PATH。"""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    bin_path = bin_dir / "fakecli"
    bin_path.write_text("@echo off\necho fakecli 1.2.3\n")
    # Windows 下要 .exe；这里以 .bat 兼容
    if os.name == "nt":
        bin_path = bin_dir / "fakecli.bat"
        bin_path.write_text("@echo off\necho fakecli 1.2.3\n")
    # PATH 加上
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return bin_path


def test_scan_one_found(fake_bin_in_path: Path) -> None:
    """路径 1：bin 在 PATH 里 → available=True, path 非空, version 探测到。"""
    name = fake_bin_in_path.stem
    # Windows .bat 去后缀
    if os.name == "nt" and name.endswith(".bat"):
        name = name[:-4]
    result = scan_one(name, timeout=2.0)
    assert isinstance(result, CliScanResult)
    assert result.available is True
    assert result.path is not None
    # Windows 上 PATH 解析会返回大写后缀，统一小写比对
    assert result.path.lower() == str(fake_bin_in_path).lower()
    assert result.error is None
    # version 可能探测到 "fakecli 1.2.3" 或 None（mock 不一定支持所有 flag）


def test_scan_one_not_found() -> None:
    """路径 2：bin 不在 PATH → available=False + error 信息。"""
    result = scan_one("definitely-not-a-real-cli-xyz123", timeout=2.0)
    assert result.available is False
    assert result.path is None
    assert result.version is None
    assert result.error is not None
    assert "not in PATH" in result.error
    assert result.last_scan_at > 0


def test_scan_all_multi_match(fake_bin_in_path: Path) -> None:
    """路径 3：scan_all 一次扫多个 bin → 顺序与输入一致，found + not-found 混合。"""
    real_name = fake_bin_in_path.stem
    if os.name == "nt" and real_name.endswith(".bat"):
        real_name = real_name[:-4]
    names = [real_name, "definitely-not-real-xyz", real_name]
    results = scan_all(names, timeout=2.0)
    assert len(results) == 3
    # 顺序一致
    assert [r.name for r in results] == names
    # 第一个 + 第三个 found
    assert results[0].available is True
    assert results[1].available is False
    assert results[2].available is True
    # found 的 path 相同
    assert results[0].path == results[2].path


def test_scan_result_to_dict() -> None:
    """附加：CliScanResult.to_dict 返回 dict 形式（API 序列化用）。"""
    result = CliScanResult(
        name="x", path="/usr/bin/x", version="1.0", available=True, last_scan_at=1.0
    )
    d = result.to_dict()
    assert d["name"] == "x"
    assert d["path"] == "/usr/bin/x"
    assert d["available"] is True
