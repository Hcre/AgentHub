"""M-C01 macOS sandbox-exec 后端.

[模块编号] M-C01
[文件职责] 通过 sandbox-exec + 自定义 SBPL profile 限制进程能力.
[设计模式] Adapter.
[关联接口契约] IC-008.
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008 + TD/S-025]
[文件依赖] asyncio.create_subprocess_exec / tempfile.
"""
from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

from agenthub.core.logging import get_logger
from agenthub.core.exceptions import SystemError, TimeoutError
from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult
from agenthub.infrastructure.sandbox.backends.base import SandboxBackend

log = get_logger(__name__)


class MacOSSandboxBackend(SandboxBackend):
    """macOS sandbox-exec 后端.

    Attributes:
        name: 固定为 "macos_sandbox".
        profile_template: SBPL profile 模板; 占位符 {memory_bytes}/{max_fds}.
    """

    name = "macos_sandbox"

    PROFILE_TEMPLATE = """(version 1)
(deny default)
(allow process-exec (literal "{cmd0}"))
(allow file-read* (subpath "/usr/lib"))
(allow sysctl-read)
(allow mach-lookup)
"""

    async def run(self, cmd: list[str], limits: Limits) -> SandboxResult:
        """通过 sandbox-exec 执行命令.

        Args:
            cmd: 命令 + 参数.
            limits: 资源配额 (仅 max_fds/nice 生效, 内存由 RLIMIT_AS 内核兜底).

        Returns:
            SandboxResult.

        Raises:
            TimeoutError: 进程超时.
            SystemError: sandbox-exec 不可用.
        """
        # TODO(impl): 实现 profile = self.PROFILE_TEMPLATE.format(cmd0=cmd[0])
        # TODO(impl): 实现 with tempfile.NamedTemporaryFile("w", suffix=".sb", delete=False) as f: f.write(profile); profile_path = f.name
        # TODO(impl): 实现 try: proc = await asyncio.create_subprocess_exec("sandbox-exec", "-f", profile_path, *cmd, stdout=PIPE, stderr=PIPE, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes)))
        # TODO(impl): 实现 except FileNotFoundError: raise SystemError(SANDBOX_BACKEND_UNAVAILABLE, "sandbox-exec not found")
        # TODO(impl): 实现 try: stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=limits.timeout_sec)
        # TODO(impl): 实现 except asyncio.TimeoutError: proc.terminate(); await asyncio.sleep(5); proc.kill(); raise TimeoutError(SANDBOX_TIMEOUT)
        # TODO(impl): 实现 finally: Path(profile_path).unlink(missing_ok=True)
        # TODO(impl): 实现 return SandboxResult(exit_code=proc.returncode, stdout=stdout[:1MB], stderr=stderr[:1MB], rss_peak=0, duration_ms=..., backend=self.name)
        ...

    async def is_available(self) -> bool:
        """探测 sandbox-exec 可用性.

        Returns:
            True 当 `which sandbox-exec` 成功.
        """
        # TODO(impl): 实现 from shutil import which; return which("sandbox-exec") is not None
        ...

    async def cleanup(self) -> None:
        """macOS sandbox-exec 进程退出即清理; no-op."""
        # TODO(impl): 实现 pass (sandbox-exec 进程退出时自动撤销 capability)
        ...
