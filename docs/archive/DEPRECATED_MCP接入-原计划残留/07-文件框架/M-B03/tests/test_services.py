"""M-B03 Binding Engine 服务测试.

[文件路径] src/agenthub/application/binding/tests/test_services.py
[文件职责] 单元测试 BindingService 编排逻辑
[所属模块] M-B03
[关联设计规范] CS-MCP-V1.0-20260602 §1.7
[测试场景]
  - test_bind_when_new_then_state_active: 新建 → Active
    Mock: repo (exists=False), generator, pool
  - test_bind_when_exists_then_conflict: 已存在 → BindingConflictError
    Mock: repo.exists=True
  - test_bind_when_lock_timeout_then_retry_once: 首次 lock 超时 → 重试 1 次成功
    Mock: generator.generate 首次抛 ConfigLockTimeoutError
  - test_unbind_when_exists_then_mark_released: 解绑 → mark_released
    Mock: repo, generator, pool
  - test_unbind_when_not_found_then_conflict: 不存在 → BindingConflictError
  - test_select_strategy_when_default_then_default: 工厂方法
  - test_select_strategy_when_unknown_then_value_error
[来源标注] [DD-M推断:服务编排标准测试]
[创建日期] 2026-06-03
[作者] DD-M-B03-20260603
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agenthub.application.binding.exceptions import BindingConflictError, ConfigLockTimeoutError
from agenthub.application.binding.schemas import BindingResult
from agenthub.application.binding.services import BindingService
from agenthub.application.binding.strategies import DefaultMappingStrategy, CustomMappingStrategy


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.exists.return_value = False
    repo.add.return_value = uuid4()
    return repo


@pytest.fixture
def mock_generator() -> AsyncMock:
    gen = AsyncMock()
    gen.generate.return_value = Path("/tmp/ws_id/mcp_id.json")
    return gen


@pytest.fixture
def mock_pool() -> MagicMock:
    pool = MagicMock()
    pool.spawn = AsyncMock(return_value={"pid": 100})
    pool.recycle = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_bind_when_new_then_state_active(mock_repo, mock_generator, mock_pool):
    # given
    svc = BindingService(generator=mock_generator, pool=mock_pool, repo=mock_repo)
    # when
    result = await svc.bind(ws_id=uuid4(), mcp_id=uuid4(), mapping=None, trace_id="t1")
    # then
    assert result.state == "Active"
    assert result.pid == 100


@pytest.mark.asyncio
async def test_bind_when_exists_then_conflict(mock_repo, mock_generator, mock_pool):
    # given
    mock_repo.exists.return_value = True
    svc = BindingService(generator=mock_generator, pool=mock_pool, repo=mock_repo)
    # when / then
    with pytest.raises(BindingConflictError):
        await svc.bind(ws_id=uuid4(), mcp_id=uuid4(), mapping=None, trace_id="t1")


@pytest.mark.asyncio
async def test_bind_when_lock_timeout_then_retry_once(mock_repo, mock_generator, mock_pool):
    # given
    mock_generator.generate.side_effect = [
        ConfigLockTimeoutError("1st"),
        Path("/tmp/ws_id/mcp_id.json"),
    ]
    svc = BindingService(generator=mock_generator, pool=mock_pool, repo=mock_repo)
    # when
    result = await svc.bind(ws_id=uuid4(), mcp_id=uuid4(), mapping=None, trace_id="t1")
    # then
    assert result.state == "Active"
    assert mock_generator.generate.call_count == 2


@pytest.mark.asyncio
async def test_unbind_when_exists_then_mark_released(mock_repo, mock_generator, mock_pool):
    # given
    mock_repo.get.return_value = BindingResult(
        binding_id=uuid4(), state="Active", config_path=Path("/tmp/x.json"), pid=100,
        ws_id=uuid4(), mcp_id=uuid4(),
    )
    svc = BindingService(generator=mock_generator, pool=mock_pool, repo=mock_repo)
    # when
    await svc.unbind(binding_id=uuid4(), trace_id="t1")
    # then
    mock_repo.mark_released.assert_called_once()
    mock_pool.recycle.assert_called_once()


@pytest.mark.asyncio
async def test_unbind_when_not_found_then_conflict(mock_repo, mock_generator, mock_pool):
    # given
    mock_repo.get.return_value = None
    svc = BindingService(generator=mock_generator, pool=mock_pool, repo=mock_repo)
    # when / then
    with pytest.raises(BindingConflictError):
        await svc.unbind(binding_id=uuid4(), trace_id="t1")


def test_select_strategy_when_default_then_default():
    s = BindingService.select_strategy("default")
    assert isinstance(s, DefaultMappingStrategy)


def test_select_strategy_when_custom_then_custom():
    s = BindingService.select_strategy("custom")
    assert isinstance(s, CustomMappingStrategy)


def test_select_strategy_when_unknown_then_value_error():
    with pytest.raises(ValueError):
        BindingService.select_strategy("weird")
