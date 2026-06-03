"""M-C01 MacOSSandboxBackend 测试场景.

[模块编号] M-C01
[文件职责] 覆盖 SBPL profile 生成、sandbox-exec 包装、profile 临时文件清理.
"""
from __future__ import annotations

import pytest

# TODO(impl): from agenthub.infrastructure.sandbox.backends.macos_sandbox import MacOSSandboxBackend
# TODO(impl): from agenthub.infrastructure.sandbox.limits import Limits


@pytest.mark.asyncio
async def test_macos_sandbox_when_run_then_create_temp_profile() -> None:
    """场景: run → 写 SBPL profile 到临时文件 → 传给 sandbox-exec -f."""
    # TODO(impl): backend = MacOSSandboxBackend()
    # TODO(impl): with patch("asyncio.create_subprocess_exec") as p, patch("tempfile.NamedTemporaryFile"):
    # TODO(impl):     p.return_value.communicate = AsyncMock(return_value=(b"", b"")); p.return_value.returncode = 0
    # TODO(impl):     await backend.run(["echo", "hi"], Limits())
    # TODO(impl):     args = p.call_args[0]
    # TODO(impl):     assert args[0] == "sandbox-exec" and args[1] == "-f"
    ...


@pytest.mark.asyncio
async def test_macos_sandbox_is_available_when_sandbox_exec_exists() -> None:
    """场景: which("sandbox-exec") 命中 → True."""
    # TODO(impl): with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
    # TODO(impl):     assert await MacOSSandboxBackend().is_available() is True
    ...


@pytest.mark.asyncio
async def test_macos_sandbox_is_available_when_sandbox_exec_missing_then_false() -> None:
    """场景: which("sandbox-exec") = None → False."""
    # TODO(impl): with patch("shutil.which", return_value=None):
    # TODO(impl):     assert await MacOSSandboxBackend().is_available() is False
    ...


@pytest.mark.asyncio
async def test_macos_sandbox_cleanup_then_no_op() -> None:
    """场景: cleanup 总是 no-op (sandbox-exec 进程退出即清理)."""
    # TODO(impl): await MacOSSandboxBackend().cleanup()  # 不应抛
    ...


@pytest.mark.asyncio
async def test_macos_sandbox_when_sandbox_exec_missing_then_raise_system_error() -> None:
    """场景: sandbox-exec 不存在 → FileNotFoundError → SystemError(SANDBOX_BACKEND_UNAVAILABLE)."""
    # TODO(impl): with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
    # TODO(impl):     with pytest.raises(SystemError) as exc: await MacOSSandboxBackend().run(["echo"], Limits())
    # TODO(impl): assert exc.value.code == "SANDBOX_BACKEND_UNAVAILABLE"
    ...
