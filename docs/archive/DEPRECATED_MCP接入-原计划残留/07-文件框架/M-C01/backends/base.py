"""M-C01 SandboxBackend 抽象基类 (Strategy 接口).

[模块编号] M-C01
[文件职责] 定义统一抽象接口, 4 个具体后端均继承本类实现 Adapter.
[设计模式] Adapter + Strategy (ABC 抽象基类).
[关联接口契约] IC-008 (API-200 sandbox.run).
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008]
[文件依赖] abc / limits.

[DD-M推断:依据] ABC 而非 Protocol, 是因为我们需要在子类构造期强制重写
name / is_available, 且后续可加入 template method (如 _pre_run 钩子).
"""
from __future__ import annotations

import abc

from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult


class SandboxBackend(abc.ABC):
    """沙箱后端抽象基类 (Strategy 接口).

    Attributes:
        name: 后端标识符 (linux_cgroup / macos_sandbox / windows_jobobj / docker).
    """

    name: str

    @abc.abstractmethod
    async def run(self, cmd: list[str], limits: Limits) -> SandboxResult:
        """执行命令并返回结果.

        Args:
            cmd: 命令与参数, 已由 Runner 校验为合法 list[str].
            limits: 资源配额 (CPU/Mem/PID/FD/timeout).

        Returns:
            SandboxResult: 退出码、stdout、stderr、rss_peak、duration_ms、killed_reason.

        Raises:
            TimeoutError: 后端实现层上报进程超时.
            SystemError: OOM 或后端不可用.
        """
        ...

    @abc.abstractmethod
    async def is_available(self) -> bool:
        """探测当前环境是否支持本后端 (Factory 调用).

        Returns:
            True 当本后端的所有依赖 (内核能力 / 命令行工具) 满足.
        """
        ...

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """进程清理 (cgroup 释放 / Job Object close / Docker container rm).

        [DD-M推断:依据] 后置条件 [IC-008] 要求资源回收, 异常路径也必须调用.
        """
        ...
