"""M-C01 Limits 与结果值对象.

[模块编号] M-C01
[文件职责] 定义 CPU/Mem/FD/PID 配额值对象 (Limits) 与执行结果值对象 (SandboxResult).
[设计模式] Value Object (frozen pydantic BaseModel, 不可变).
[关联接口契约] IC-008 (API-200 sandbox.run 入参 limits + 出参).
[关联上游设计] [DD-001:MD/M-C01 + IC/IC-008]
[文件依赖] pydantic (BaseModel).
[下游使用] SandboxRunner / 各 Backend.

[DD-M推断:依据] Limits 不可变以避免多线程场景下后端读到半修改的配额,
SandboxResult 不可变以保证调用方可以安全地传递给上层 Saga 上下文.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class Limits(BaseModel):
    """沙箱进程资源配额值对象.

    Attributes:
        cpu_quota_us: CPU 配额 (微秒), 默认 100000 = 1 vCPU 满载.
        memory_bytes: 内存上限 (字节), 默认 512 MiB.
        max_pids: 最大子进程数, 默认 32 (防止 fork bomb).
        max_fds: 最大文件描述符数, 默认 256.
        timeout_sec: 进程执行超时, 默认 30s.
        niceness: 进程优先级 (-20 ~ 19), 默认 0.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cpu_quota_us: int = Field(default=100_000, ge=1_000, le=10_000_000)
    memory_bytes: int = Field(default=512 * 1024 * 1024, ge=16 * 1024 * 1024)
    max_pids: int = Field(default=32, ge=1, le=1024)
    max_fds: int = Field(default=256, ge=16, le=65536)
    timeout_sec: int = Field(default=30, ge=1, le=600)
    niceness: int = Field(default=0, ge=-20, le=19)


class SandboxResult(BaseModel):
    """沙箱执行结果值对象.

    Attributes:
        exit_code: 进程退出码 (0=正常, 137=SIGKILL, 143=SIGTERM).
        stdout: 标准输出字节流 (上限 1 MiB, 超出截断).
        stderr: 标准错误字节流 (上限 1 MiB, 超出截断).
        rss_peak: 进程执行期间 RSS 峰值 (字节).
        duration_ms: 实际执行耗时 (毫秒).
        backend: 实际使用的后端标识 (linux_cgroup / macos_sandbox / windows_jobobj / docker).
        killed_reason: 进程被杀原因 (timeout / oom / sigkill / None).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    exit_code: int
    stdout: bytes
    stderr: bytes
    rss_peak: int
    duration_ms: int
    backend: Literal["linux_cgroup", "macos_sandbox", "windows_jobobj", "docker"]
    killed_reason: Literal["timeout", "oom", "sigkill", None] = None
