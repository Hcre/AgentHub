"""M-C01 SandboxRunner 测试场景.

[模块编号] M-C01
[文件职责] 覆盖 runner.py 的 cmd 校验、并发上限、timeout 降级、backend 不可用.
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008] (用例数 10, 见 MD 模块细化)
[命名规范] [DD-001:CS §1.7] test_{function}_when_{scenario}_then_{expected}
"""
from __future__ import annotations

import pytest

# TODO(impl): from agenthub.core.exceptions import ValidationError, TimeoutError, SystemError
# TODO(impl): from agenthub.infrastructure.sandbox.runner import SandboxRunner
# TODO(impl): from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult


@pytest.mark.asyncio
async def test_runner_when_cmd_is_str_then_raise_validation_error() -> None:
    """场景: cmd 传 str (shell 拼接风险 [TD:S-026]) → 应抛 ValidationError(SANDBOX_INVALID_CMD)."""
    # TODO(impl): runner = SandboxRunner.__new__(SandboxRunner)  # 跳过构造探测
    # TODO(impl): runner._semaphore = asyncio.Semaphore(5)
    # TODO(impl): with pytest.raises(ValidationError) as exc: await runner.run("ls -la")
    # TODO(impl): assert exc.value.code == "SANDBOX_INVALID_CMD"
    ...


@pytest.mark.asyncio
async def test_runner_when_cmd_contains_shell_metachar_then_raise_validation_error() -> None:
    """场景: cmd 元素含 ; & | $ ` 等元字符 → 拒绝."""
    # TODO(impl): runner = SandboxRunner.__new__(SandboxRunner)
    # TODO(impl): with pytest.raises(ValidationError) as exc: await runner.run(["ls", "a;b"])
    # TODO(impl): assert exc.value.code == "SANDBOX_INVALID_CMD"
    ...


@pytest.mark.asyncio
async def test_runner_when_cmd_is_valid_list_then_delegate_to_backend() -> None:
    """场景: 合法 list[str] cmd → 透传到 backend.run, 返回 SandboxResult."""
    # TODO(impl): fake_backend = AsyncMock()
    # TODO(impl): fake_backend.run.return_value = SandboxResult(exit_code=0, stdout=b"", stderr=b"", rss_peak=0, duration_ms=10, backend="linux_cgroup")
    # TODO(impl): runner = SandboxRunner(backend=fake_backend)
    # TODO(impl): result = await runner.run(["echo", "hi"])
    # TODO(impl): fake_backend.run.assert_awaited_once()
    # TODO(impl): assert result.exit_code == 0
    ...


@pytest.mark.asyncio
async def test_runner_when_backend_timeout_then_send_sigterm_then_sigkill() -> None:
    """场景: backend.run 超时 → SIGTERM → 5s → SIGKILL → 抛 TimeoutError(SANDBOX_TIMEOUT)."""
    # TODO(impl): fake_backend = AsyncMock()
    # TODO(impl): fake_backend.run.side_effect = asyncio.TimeoutError()
    # TODO(impl): fake_proc = MagicMock(); fake_proc.terminate = MagicMock(); fake_proc.kill = MagicMock(); fake_proc.wait = AsyncMock()
    # TODO(impl): runner = SandboxRunner(backend=fake_backend)
    # TODO(impl): with pytest.raises(TimeoutError) as exc: await runner.run(["sleep", "60"], timeout_sec=1)
    # TODO(impl): assert exc.value.code == "SANDBOX_TIMEOUT"
    ...


@pytest.mark.asyncio
async def test_runner_when_oom_from_cgroup_then_mark_killed_oom() -> None:
    """场景: cgroup memory.events OOM kill → SandboxResult.killed_reason == "oom"."""
    # TODO(impl): fake_backend = AsyncMock()
    # TODO(impl): fake_backend.run.return_value = SandboxResult(exit_code=137, stdout=b"", stderr=b"Killed", rss_peak=512*1024*1024, duration_ms=100, backend="linux_cgroup", killed_reason="oom")
    # TODO(impl): runner = SandboxRunner(backend=fake_backend)
    # TODO(impl): result = await runner.run(["python", "-c", "x=[]; x.append(x)"])
    # TODO(impl): assert result.killed_reason == "oom"
    ...


@pytest.mark.asyncio
async def test_runner_when_concurrency_exceeds_5_then_semaphore_blocks() -> None:
    """场景: per-node 5 并发上限, 第 6 个 await 阻塞直到前 5 完成 [IC-008]."""
    # TODO(impl): fake_backend = AsyncMock(); fake_backend.run.side_effect = lambda c, l: asyncio.sleep(0.1)
    # TODO(impl): runner = SandboxRunner(backend=fake_backend)
    # TODO(impl): coros = [runner.run(["echo", str(i)]) for i in range(6)]
    # TODO(impl): start = time.monotonic(); await asyncio.gather(*coros); elapsed = time.monotonic() - start
    # TODO(impl): assert elapsed >= 0.2  # 至少 2 批, 即 ≥ 0.2s
    ...


@pytest.mark.asyncio
async def test_runner_when_backend_unavailable_then_raise_system_error() -> None:
    """场景: Factory 探测 4 后端均不可用 → SystemError(SANDBOX_BACKEND_UNAVAILABLE)."""
    # TODO(impl): from agenthub.infrastructure.sandbox.factory import SandboxFactory
    # TODO(impl): SandboxFactory._cached_backend = None
    # TODO(impl): with patch("platform.system", return_value="UnknownOS"), patch.object(SandboxFactory, "_docker_available", return_value=False):
    # TODO(impl):     with pytest.raises(SystemError) as exc: SandboxFactory.get_backend()
    # TODO(impl): assert exc.value.code == "SANDBOX_BACKEND_UNAVAILABLE"
    ...


@pytest.mark.asyncio
async def test_runner_when_command_exit_nonzero_then_return_exit_code() -> None:
    """场景: 进程 exit_code != 0 → 不抛异常, 仅透传 exit_code (业务判别)."""
    # TODO(impl): fake_backend = AsyncMock()
    # TODO(impl): fake_backend.run.return_value = SandboxResult(exit_code=2, stdout=b"", stderr=b"err", rss_peak=0, duration_ms=5, backend="linux_cgroup")
    # TODO(impl): runner = SandboxRunner(backend=fake_backend)
    # TODO(impl): result = await runner.run(["false"])
    # TODO(impl): assert result.exit_code == 2
    ...


@pytest.mark.asyncio
async def test_runner_when_cmd_is_empty_list_then_raise_validation_error() -> None:
    """场景: cmd=[] 空列表 → 拒绝 (无命令执行)."""
    # TODO(impl): runner = SandboxRunner.__new__(SandboxRunner)
    # TODO(impl): with pytest.raises(ValidationError): await runner.run([])
    ...


@pytest.mark.asyncio
async def test_runner_when_stdout_exceeds_1mb_then_truncate() -> None:
    """场景: backend 返回 stdout > 1MB → SandboxResult.stdout 截断到 1MB [IC-008]."""
    # TODO(impl): fake_backend = AsyncMock()
    # TODO(impl): fake_backend.run.return_value = SandboxResult(exit_code=0, stdout=b"x" * (2 * 1024 * 1024), stderr=b"", rss_peak=0, duration_ms=5, backend="linux_cgroup")
    # TODO(impl): runner = SandboxRunner(backend=fake_backend)
    # TODO(impl): result = await runner.run(["yes"])
    # TODO(impl): assert len(result.stdout) == 1024 * 1024
    ...
