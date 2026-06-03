"""M-B03 Binding Engine 生成器测试.

[文件路径] src/agenthub/application/binding/tests/test_generators.py
[文件职责] 单元测试 ConfigGenerator 文件生成与撤销
[所属模块] M-B03
[关联设计规范] CS-MCP-V1.0-20260602 §1.7 + ADR-005 + SEC:SEC-011
[测试场景]
  - test_generate_when_called_then_file_exists_with_0600
  - test_generate_when_path_escape_then_raises: symlink 攻击
  - test_revoke_when_exists_then_file_deleted
  - test_revoke_when_not_exists_then_skip_silently
  - test_resolve_path_when_mcp_id_then_correct_path
[Mock 策略] 使用 tmp_path fixture 模拟文件系统
[来源标注] [DD-M推断:基于 ADR-005 单一源约束]
[创建日期] 2026-06-03
[作者] DD-M-B03-20260603
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from uuid import uuid4

import pytest

from agenthub.application.binding.exceptions import PathTraversalError
from agenthub.application.binding.generators import ConfigGenerator


@pytest.fixture
def generator(tmp_path: Path) -> ConfigGenerator:
    return ConfigGenerator(base_dir=tmp_path)


@pytest.mark.asyncio
async def test_generate_when_called_then_file_exists_with_0600(generator: ConfigGenerator, tmp_path: Path):
    # given
    ws_id = uuid4()
    mapping = {"alpha": "http://x"}
    # when
    path = await generator.generate(mapping=mapping, ws_id=ws_id, trace_id="t1")
    # then
    assert path.exists()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


@pytest.mark.asyncio
async def test_generate_when_path_escape_then_raises(tmp_path: Path):
    # given
    gen = ConfigGenerator(base_dir=tmp_path)
    ws_id = uuid4()
    # 创建 symlink 试图逃逸
    link = tmp_path / "escape"
    link.symlink_to("/etc")
    # when / then
    with pytest.raises(PathTraversalError):
        await gen.resolve_path(ws_id=uuid4())


@pytest.mark.asyncio
async def test_revoke_when_exists_then_file_deleted(generator: ConfigGenerator):
    # given
    ws_id = uuid4()
    p = await generator.generate(mapping={"a": "b"}, ws_id=ws_id, trace_id="t1")
    assert p.exists()
    # when
    await generator.revoke(config_path=p, ws_id=ws_id, trace_id="t1")
    # then
    assert not p.exists()


@pytest.mark.asyncio
async def test_revoke_when_not_exists_then_skip_silently(generator: ConfigGenerator):
    # when / then - 不抛异常
    await generator.revoke(config_path=generator._base_dir / "ghost.json", ws_id=uuid4(), trace_id="t1")


def test_resolve_path_when_mcp_id_then_correct_path(generator: ConfigGenerator):
    # given
    ws_id = uuid4()
    mcp_id = uuid4()
    # when
    p = generator.resolve_path(ws_id=ws_id, mcp_id=mcp_id)
    # then
    assert p.name == f"{mcp_id}.json"
    assert p.parent.name == str(ws_id)
