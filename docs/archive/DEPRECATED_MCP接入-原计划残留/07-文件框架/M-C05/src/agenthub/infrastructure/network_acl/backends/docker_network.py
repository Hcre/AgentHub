"""M-C05 Docker Network backend.

[文件路径] src/agenthub/infrastructure/network_acl/backends/docker_network.py
[文件职责] 通过 Docker network / iptables-in-container 管理 ACL
[所属模块] M-C05（来自DD-001）
[关联设计规范] FS-014 / MD-MCP-V1.0-20260602#M-C05
[功能描述]
  功能1: 通过 Docker SDK 连接 network + 增删 ACL
  功能2: 容器内 iptables 注入
[输入输出]
  输入: ACLRule / rule_id
  输出: Docker SDK 返回值 / 异常
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../controller.py
[注意事项]
  注意1: 仅当 workspace 进程运行于 Docker 时选用
  注意2: 需要 Docker socket 挂载或远程 daemon
  注意3: 超时 10s（CS-001）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C05 - 初始框架
[作者] DD-M-C05-2026-06-03
[来源标注] [DD-001:FS-014/MD-MCP-V1.0-20260602#M-C05]
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from agenthub.core.logging import get_logger

from agenthub.infrastructure.network_acl.backends.base import ACLBackend

if TYPE_CHECKING:
    from agenthub.infrastructure.network_acl.controller import ACLRule


log = get_logger(__name__)


class DockerNetworkBackend(ACLBackend):
    """Docker Network backend 实现.

    [类名] DockerNetworkBackend
    [职责] 容器化 workspace 的网络 ACL 管理
    [关联设计规范] MD-MCP-V1.0-20260602#M-C05
    [属性]
      属性1: name str = "docker_network"
      属性2: network_name str 目标 Docker network 名
    [方法列表]
      方法1: apply(rules) → list[UUID]
      方法2: revoke(rule_id) → None
      方法3: healthcheck() → bool
    [状态机] 无
    [异常处理]
      异常1: ACLBackendUnavailable 503 - Docker daemon 不可达
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
    """

    name: str = "docker_network"

    async def apply(self, rules: list[ACLRule]) -> list[uuid.UUID]:
        """通过 Docker SDK 应用规则.

        [函数名] apply
        [职责] 调用 aiodocker 客户端增删 network ACL
        [关联接口契约] IC-012 后端实现
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        ...

    async def revoke(self, rule_id: uuid.UUID) -> None:
        """撤销 Docker network 规则.

        [函数名] revoke
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        ...

    async def healthcheck(self) -> bool:
        """探测 Docker daemon 可达.

        [函数名] healthcheck
        [职责] aiodocker ping
        [来源标注] [DD-M推断:参考 M-C01 SandboxFactory 探测]
        """
        ...
