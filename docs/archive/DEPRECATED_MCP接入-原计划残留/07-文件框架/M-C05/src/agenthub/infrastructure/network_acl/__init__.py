"""M-C05 Network ACL 模块包初始化.

[文件路径] src/agenthub/infrastructure/network_acl/__init__.py
[文件职责] M-C05 Network ACL 模块公共接口导出
[所属模块] M-C05（来自DD-001）
[关联设计规范] FS-014 / MD-MCP-V1.0-20260602#M-C05
[功能描述]
  功能1: 导出 ACLController / ACLBackend / 各后端实现
  功能2: 暴露模块版本号与公共常量
[输入输出]
  输入: 外部 from agenthub.infrastructure.network_acl import ...
  输出: Controller / Backend 抽象 / 具体后端类
[依赖关系]
  依赖文件: ./controller.py, ./backends/base.py, ./backends/iptables.py,
            ./backends/docker_network.py, ./backends/ipset.py
  被依赖文件: agenthub.application.binding（[DD-M推断:通过 service 层调用]）
[注意事项]
  注意1: 禁止在本 __init__ 中执行 IO 或 backend 探测（延迟到 controller 初始化）
  注意2: backend 选型应交由 SandboxFactory 风格的工厂或运行期探测
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C05 - 初始版本，仅含注释与导出占位
[作者] DD-M-C05-2026-06-03
[来源标注] [DD-001:FS-014/MD-MCP-V1.0-20260602#M-C05]
"""
from __future__ import annotations

# [DD-M推断:FS-014 未列出本文件，但 src-layout 最佳实践要求包级 __init__.py]

__all__: list[str] = [
    "ACLController",
    "ACLBackend",
    "IptablesBackend",
    "DockerNetworkBackend",
    "IpsetBackend",
    "ACLRule",
    "MODULE_VERSION",
]

MODULE_VERSION: str = "1.0.0"
