"""M-C01 Docker 后端 (WSL2 兜底 / 跨平台).

[模块编号] M-C01
[文件职责] 通过 Docker CLI 启动一次性容器执行命令, 兜底 WSL2 与无原生后端场景.
[设计模式] Adapter.
[关联接口契约] IC-008.
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008 + TD/TD-003 + TS-023]
[文件依赖] asyncio.create_subprocess_exec / shutil.

[DD-M推断:依据] Docker 后端是最后兜底, 因此必须严格:
- 每次执行创建独立容器 (--rm) 避免状态污染;
- 使用只读根 FS + tmpfs /tmp 限制写入;
- network=none 阻断外联 (与 M-C06 SSRF 防御对齐).
"""
from __future__ import annotations

import asyncio
import shutil
import time
import uuid

from agenthub.core.logging import get_logger
from agenthub.core.exceptions import SystemError, TimeoutError
from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult
from agenthub.infrastructure.sandbox.backends.base import SandboxBackend

log = get_logger(__name__)


class DockerBackend(SandboxBackend):
    """Docker 后端 (WSL2 / 跨平台兜底).

    Attributes:
        name: 固定为 "docker".
        image: 基础镜像, 默认 "python:3.11-slim".
    """

    name = "docker"

    def __init__(self, image: str = "python:3.11-slim") -> None:
        """初始化.

        Args:
            image: 容器镜像; 镜像必须存在否则启动失败.
        """
        # TODO(impl): 实现 self._image = image
        ...

    async def run(self, cmd: list[str], limits: Limits) -> SandboxResult:
        """通过 docker run 执行命令.

        Args:
            cmd: 命令 + 参数 (在容器内执行).
            limits: 资源配额, 映射到 --cpus / --memory / --pids-limit.

        Returns:
            SandboxResult.

        Raises:
            TimeoutError: 容器启动 + 执行超时.
            SystemError: docker run 失败或镜像不存在.
        """
        # TODO(impl): 实现 cpus = limits.cpu_quota_us / 1_000_000  # 1 vCPU = 1_000_000us
        # TODO(impl): 实现 container_name = f"mcp-sandbox-{uuid4().hex[:12]}"
        # TODO(impl): 实现 args = ["docker", "run", "--rm", "--name", container_name, "--network=none", "--read-only", "--tmpfs", "/tmp:size=64m", "--cpus", str(cpus), "--memory", str(limits.memory_bytes), "--pids-limit", str(limits.max_pids), self._image, *cmd]
        # TODO(impl): 实现 start = time.monotonic()
        # TODO(impl): 实现 try: proc = await asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=PIPE)
        # TODO(impl): 实现     stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=limits.timeout_sec)
        # TODO(impl): 实现 except asyncio.TimeoutError: await self._stop_container(container_name); raise TimeoutError(SANDBOX_TIMEOUT)
        # TODO(impl): 实现 return SandboxResult(exit_code=proc.returncode, stdout=stdout[:1MB], stderr=stderr[:1MB], rss_peak=0, duration_ms=int((time.monotonic()-start)*1000), backend=self.name)
        ...

    async def is_available(self) -> bool:
        """探测 Docker daemon + 镜像存在.

        Returns:
            True 当 `docker version` 退出码 0 且 self._image 存在.
        """
        # TODO(impl): 实现 from shutil import which; if which("docker") is None: return False
        # TODO(impl): 实现 proc = await asyncio.create_subprocess_exec("docker", "image", "inspect", self._image, stdout=DEVNULL, stderr=DEVNULL)
        # TODO(impl): 实现 rc = await asyncio.wait_for(proc.wait(), timeout=2); return rc == 0
        ...

    async def cleanup(self) -> None:
        """清理残留容器 (异常路径调用)."""
        # TODO(impl): 实现 for name in self._active_containers: await self._stop_container(name)
        ...

    async def _stop_container(self, name: str) -> None:
        """docker stop + rm.

        Args:
            name: 容器名.
        """
        # TODO(impl): 实现 proc = await asyncio.create_subprocess_exec("docker", "rm", "-f", name, stdout=DEVNULL, stderr=DEVNULL)
        # TODO(impl): 实现 try: await asyncio.wait_for(proc.wait(), timeout=10)
        # TODO(impl): 实现 except asyncio.TimeoutError: log.error("docker_cleanup_timeout", name=name)
        ...
