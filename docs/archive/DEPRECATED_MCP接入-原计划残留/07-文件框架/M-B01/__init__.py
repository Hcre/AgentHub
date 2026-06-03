"""M-B01 Market Service 模块入口.

[文件路径] src/agenthub/application/market/__init__.py
[文件职责] 导出 Market Service 公共接口，初始化模块日志
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-MCP-V1.0-20260602#FS-005
[功能描述]
  功能1: 导出 MarketController、MarketService、MCPServerRepository、CachedMCPServerRepository
  功能2: 集中暴露模块级 DTO 契约（ListFilter / Page / MCPServerDTO / MCPServerDetail）
[输入输出]
  输入: 无（模块加载期）
  输出: 公共符号包，供 API Gateway (M-A01) 路由挂载
[依赖关系]
  依赖文件: agenthub.core.logging、agenthub.application.market.controllers/services/repositories/decorators/schemas
  被依赖文件: agenthub.access.api_gateway（M-A01 在 router 注册时导入）
[注意事项]
  注意1: 禁止在此处执行任何 IO（cache 客户端等）— 仅做符号聚合与单例解引用
  注意2: 严禁循环导入到下层业务模块，import 必须自上而下（controllers→services→repositories→schemas）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1（Python 风格）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-B01 - 初版模块入口
[作者] DD-M-B01-20260602
[来源标注] [DD-001:FS-005/MD-MCP#M-B01]
"""
from __future__ import annotations

from agenthub.application.market.controllers import MarketController
from agenthub.application.market.decorators import CachedMCPServerRepository
from agenthub.application.market.repositories import MCPServerRepository
from agenthub.application.market.schemas import (
    ListFilter,
    MCPServerDTO,
    MCPServerDetail,
    Page,
)
from agenthub.application.market.services import MarketService

__all__: list[str] = [
    "MarketController",
    "MarketService",
    "MCPServerRepository",
    "CachedMCPServerRepository",
    "ListFilter",
    "MCPServerDTO",
    "MCPServerDetail",
    "Page",
]
