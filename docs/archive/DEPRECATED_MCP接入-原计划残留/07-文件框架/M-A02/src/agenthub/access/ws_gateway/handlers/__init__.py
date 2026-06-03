"""WS Event Gateway handlers 子包 (M-A02).

[文件路径] src/agenthub/access/ws_gateway/handlers/__init__.py
[文件职责] handlers 子包初始化，导出 register 函数
[所属模块] M-A02
[关联设计规范] MD-M-A02 / FS-002
[来源标注] [DD-001:FS-002 子模块拆分 ws_server/]
[创建日期] 2026-06-02
[作者] DD-M-A02
"""

from __future__ import annotations

from agenthub.access.ws_gateway.handlers import connect, ping, subscribe

__all__ = ["connect", "subscribe", "ping"]
