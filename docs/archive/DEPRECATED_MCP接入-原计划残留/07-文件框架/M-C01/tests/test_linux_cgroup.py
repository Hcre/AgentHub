"""M-C01 LinuxCgroupBackend 测试场景.

[模块编号] M-C01
[文件职责] 覆盖 systemd-run 包装、cgroup 配额映射、cleanup 幂等.
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008 + TD/S-025]
"""
from __future__ import annotations

import pytest

# TODO(impl): from agenthub.infrastructure.sandbox.backends.linux_cgroup import LinuxCgroupBackend
# TODO(impl): from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult


@pytest.mark.asyncio
async def test_linux_cgroup_when_run_echo_then_pass_through_systemd_run() -> None:
    """场景: run ["echo", "hi"] → systemd-run --scope -p CPUQuota ... -p MemoryMax ... echo hi."""
    # TODO(impl): backend = LinuxCgroupBackend()
    # TODO(impl): with patch("asyncio.create_subprocess_exec") as p: p.return_value.communicate = AsyncMock(return_value=(b"hi\n", b""))
    # TODO(impl):     p.return_value.returncode = 0
    # TODO(impl):     result = await backend.run(["echo", "hi"], Limits())
    # TODO(impl):     args = p.call_args[0]
    # TODO(impl):     assert args[0] == "systemd-run"
    # TODO(impl):     assert "-p" in args and "CPUQuota=100000us" in args
    # TODO(impl):     assert result.exit_code == 0
    ...


@pytest.mark.asyncio
async def test_linux_cgroup_when_memory_exceeded_then_killed_oom() -> None:
    """场景: 进程 OOM → cgroup memory.events 触发 SIGKILL → exit_code=137."""
    # TODO(impl): backend = LinuxCgroupBackend()
    # TODO(impl): with patch("asyncio.create_subprocess_exec") as p: p.return_value.communicate = AsyncMock(return_value=(b"", b"Killed"))
    # TODO(impl):     p.return_value.returncode = 137
    # TODO(impl):     with patch.object(backend, "_read_peak", return_value=512*1024*1024):
    # TODO(impl):         result = await backend.run(["python", "-c", "pass"], Limits(memory_bytes=64*1024*1024))
    # TODO(impl): assert result.killed_reason == "oom"
    ...


@pytest.mark.asyncio
async def test_linux_cgroup_is_available_when_cgroup_v2_and_systemd_run() -> None:
    """场景: cgroup v2 文件存在 + systemd-run 可执行 → True."""
    # TODO(impl): with patch("pathlib.Path.exists", return_value=True), patch("shutil.which", return_value="/usr/bin/systemd-run"):
    # TODO(impl):     assert await LinuxCgroupBackend().is_available() is True
    ...


@pytest.mark.asyncio
async def test_linux_cgroup_is_available_when_no_cgroup_v2_then_false() -> None:
    """场景: cgroup v2 文件缺失 → False."""
    # TODO(impl): with patch("pathlib.Path.exists", return_value=False):
    # TODO(impl):     assert await LinuxCgroupBackend().is_available() is False
    ...


@pytest.mark.asyncio
async def test_linux_cgroup_cleanup_when_unit_stopped_then_handle_closed() -> None:
    """场景: cleanup_unit → systemctl stop → 句柄关闭."""
    # TODO(impl): backend = LinuxCgroupBackend()
    # TODO(impl): with patch("asyncio.create_subprocess_exec") as p: p.return_value.wait = AsyncMock(return_value=0)
    # TODO(impl):     await backend.cleanup_unit("mcp-sandbox-abc.service")
    # TODO(impl):     args = p.call_args[0]; assert args[:2] == ("systemctl", "stop")
    ...
