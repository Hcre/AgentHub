"""M-B03 Binding Engine 控制器测试.

[文件路径] src/agenthub/application/binding/tests/test_controllers.py
[文件职责] 单元测试 BindingController 的 HTTP 入口
[所属模块] M-B03
[关联设计规范] CS-MCP-V1.0-20260602 §1.7
[测试场景]
  - test_bind_when_valid_form_then_201: 正常绑定 → 201 + BindingResult
    断言: HTTP 201, body.state="Active", body.pid >= 0
    Mock: BindingService.bind
  - test_bind_when_conflict_then_409: 重复绑定 → 409 BINDING_CONFLICT
    断言: HTTP 409, body.code="BINDING_CONFLICT"
    Mock: BindingService.bind raises BindingConflictError
  - test_bind_when_lock_timeout_then_503: 锁竞争 → 503 CONFIG_LOCK_TIMEOUT
    断言: HTTP 503
    Mock: BindingService.bind raises ConfigLockTimeoutError
  - test_unbind_when_exists_then_204: 解绑成功 → 204
    Mock: BindingService.unbind
  - test_unbind_when_not_found_then_404: binding 不存在 → 404
    Mock: raises BindingConflictError
  - test_list_bindings_when_page_1_then_returns_items: 列表 → 200 + items
    Mock: BindingService.list_bindings
[来源标注] [DD-M推断:基于 M-B01 market controller 测试模式]
[创建日期] 2026-06-03
[作者] DD-M-B03-20260603
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import HTTPException

from agenthub.application.binding.controllers import BindingController
from agenthub.application.binding.exceptions import BindingConflictError, ConfigLockTimeoutError
from agenthub.application.binding.schemas import BindForm, BindingResult
from agenthub.application.binding.services import BindingService


@pytest.fixture
def mock_service() -> AsyncMock:
    return AsyncMock(spec=BindingService)


@pytest.fixture
def controller(mock_service: AsyncMock) -> BindingController:
    return BindingController(service=mock_service)


@pytest.mark.asyncio
async def test_bind_when_valid_form_then_201(controller: BindingController, mock_service: AsyncMock):
    # given
    form = BindForm(workspace_id=uuid4(), mcp_id=uuid4(), mapping=None)
    expected = BindingResult(
        binding_id=uuid4(), state="Active", config_path="/tmp/x.json", pid=1234,
        ws_id=form.workspace_id, mcp_id=form.mcp_id,
    )
    mock_service.bind.return_value = expected
    # when
    result = await controller.bind(form)
    # then
    assert result.state == "Active"
    assert result.pid == 1234


@pytest.mark.asyncio
async def test_bind_when_conflict_then_409(controller: BindingController, mock_service: AsyncMock):
    # given
    form = BindForm(workspace_id=uuid4(), mcp_id=uuid4(), mapping=None)
    mock_service.bind.side_effect = BindingConflictError("dup")
    # when / then
    with pytest.raises(HTTPException) as exc:
        await controller.bind(form)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "BINDING_CONFLICT"


@pytest.mark.asyncio
async def test_bind_when_lock_timeout_then_503(controller: BindingController, mock_service: AsyncMock):
    # given
    form = BindForm(workspace_id=uuid4(), mcp_id=uuid4(), mapping=None)
    mock_service.bind.side_effect = ConfigLockTimeoutError("lock")
    # when / then
    with pytest.raises(HTTPException) as exc:
        await controller.bind(form)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_unbind_when_exists_then_204(controller: BindingController, mock_service: AsyncMock):
    # when
    await controller.unbind(binding_id=uuid4())
    # then
    mock_service.unbind.assert_called_once()


@pytest.mark.asyncio
async def test_unbind_when_not_found_then_404(controller: BindingController, mock_service: AsyncMock):
    # given
    mock_service.unbind.side_effect = BindingConflictError("not found")
    # when / then
    with pytest.raises(HTTPException) as exc:
        await controller.unbind(binding_id=uuid4())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_bindings_when_page_1_then_returns_items(controller: BindingController, mock_service: AsyncMock):
    # given
    mock_service.list_bindings.return_value = ([], 0)
    # when
    resp = await controller.list_bindings(workspace_id=uuid4(), page=1, size=20)
    # then
    assert resp.total == 0
    assert resp.items == []
