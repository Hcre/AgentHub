"""M-C01 WindowsJobObjBackend 测试场景.

[模块编号] M-C01
[文件职责] 覆盖 pywin32 Job Object 创建、CPU/Mem 配额、KillOnJobClose.
"""
from __future__ import annotations

import sys
import pytest

# TODO(impl): from agenthub.infrastructure.sandbox.backends.windows_jobobj import WindowsJobObjBackend
# TODO(impl): from agenthub.infrastructure.sandbox.limits import Limits


@pytest.mark.skipif(sys.platform != "win32", reason="windows-only test")
def test_windows_jobobj_construct_on_non_windows_then_raise() -> None:
    """场景: 非 Windows 平台构造 → SystemError(SANDBOX_BACKEND_UNAVAILABLE)."""
    # TODO(impl): with patch.object(sys, "platform", "linux"):
    # TODO(impl):     with pytest.raises(SystemError) as exc: WindowsJobObjBackend()
    # TODO(impl): assert exc.value.code == "SANDBOX_BACKEND_UNAVAILABLE"
    ...


@pytest.mark.asyncio
async def test_windows_jobobj_run_then_assign_process_to_job() -> None:
    """场景: run → CreateJobObject + AssignProcessToJobObject."""
    # TODO(impl): with patch.dict(sys.modules, {"win32job": MagicMock()}):
    # TODO(impl):     backend = WindowsJobObjBackend()
    # TODO(impl):     with patch("asyncio.create_subprocess_exec") as p: p.return_value.communicate = AsyncMock(return_value=(b"", b"")); p.return_value.returncode = 0
    # TODO(impl):         await backend.run(["cmd", "/c", "echo"], Limits())
    # TODO(impl):         win32job = sys.modules["win32job"]
    # TODO(impl):         win32job.AssignProcessToJobObject.assert_called()
    ...


@pytest.mark.asyncio
async def test_windows_jobobj_is_available_when_win32_and_pywin32() -> None:
    """场景: Windows + import win32job 成功 → True."""
    # TODO(impl): with patch.object(sys, "platform", "win32"), patch.dict(sys.modules, {"win32job": MagicMock()}):
    # TODO(impl):     assert await WindowsJobObjBackend().is_available() is True
    ...


@pytest.mark.asyncio
async def test_windows_jobobj_is_available_when_pywin32_missing_then_false() -> None:
    """场景: import win32job 失败 → False."""
    # TODO(impl): with patch.object(sys, "platform", "win32"), patch.dict(sys.modules, {"win32job": None}):
    # TODO(impl):     assert await WindowsJobObjBackend().is_available() is False
    ...
