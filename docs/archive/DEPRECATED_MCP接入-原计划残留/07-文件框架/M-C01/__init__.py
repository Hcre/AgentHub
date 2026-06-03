"""M-C01 Sandbox Engine 模块入口.

[模块编号] M-C01
[模块名称] Sandbox Engine
[关联技术选型] TS-001 Python 3.11 / TS-020 pywin32 / TS-023 Docker / OS 原生（cgroup v2 / sandbox-exec）
[设计模式] Adapter + Strategy + Factory + Abstract Backend
[关联接口契约] IC-008 (API-200 sandbox.run)
[关联模块细化] [DD-001:MD/M-C01]
[关联文件结构] [DD-001:FS-010]
[关联异常策略] [DD-001:EX-002 + EX-004 + EX-018]
[关联上游依赖] 无（基础设施层 leaf 模块）
[关联下游消费方] M-B02 ProcessPoolManager（pool.spawn 调用 backend.run）

本模块对外暴露统一接口 sandbox.run(cmd: list[str], limits: Limits) -> SandboxResult,
通过 SandboxFactory 自适应选择 Linux cgroup / macOS sandbox-exec / Windows Job Object /
Docker 四种后端之一。强制 list[str] 入参以阻断 shell 注入探测 [TD:S-026]。
"""
from agenthub.infrastructure.sandbox.runner import SandboxRunner
from agenthub.infrastructure.sandbox.factory import SandboxFactory
from agenthub.infrastructure.sandbox.limits import Limits, SandboxResult
from agenthub.infrastructure.sandbox.backends.base import SandboxBackend

__all__ = [
    "SandboxRunner",
    "SandboxFactory",
    "SandboxBackend",
    "Limits",
    "SandboxResult",
]

__m_id__ = "M-C01"
__version__ = "1.0.0"
