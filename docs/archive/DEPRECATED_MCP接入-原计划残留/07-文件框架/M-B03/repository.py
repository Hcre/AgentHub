"""M-B03 Binding Engine 仓储接口.

[文件路径] src/agenthub/application/binding/repository.py
[文件职责] 定义 BindingRepository 抽象接口（实现由 M-D01 提供）
[所属模块] M-B03
[关联设计规范] MD-MCP-V1.0-20260602#M-B03 + DS-002 mcp_installations
[功能描述]
  功能1: BindingRepository ABC 定义 exists / add / get / list / mark_released
  功能2: 由 M-D01 UnitOfWork 提供 PG 实现
[输入输出]
  输入: ws_id / mcp_id / binding_id / page / size
  输出: bool / UUID / BindingResult / list / None
[依赖关系]
  依赖文件: agenthub.application.binding.schemas
  被依赖文件: agenthub.application.binding.services
[注意事项]
  注意1: 抽象接口仅定义契约，PG 实现由 M-D01 提供
  注意2: 唯一约束 (mcp_id, workspace_id) 由 DB 层保证
  注意3: 列表分页基于 (ws_id, created_at DESC) 索引
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版仓储接口
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + DS-002 + MD-MCP-V1.0-20260602#M-B03]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID

from agenthub.application.binding.schemas import BindingResult, Mapping


class BindingRepository(ABC):
    """绑定仓储抽象接口.

    [类名] BindingRepository
    [职责] 定义 binding 表 CRUD 契约
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03 + DS-002
    [属性] (无)
    [方法列表]
      方法1: exists(ws_id, mcp_id) -> bool - 检查绑定是否存在
      方法2: add(ws_id, mcp_id, mapping, config_path, pid, trace_id) -> UUID - 插入
      方法3: get(binding_id) -> BindingResult | None - 查询单条
      方法4: list(ws_id, page, size, trace_id) -> tuple[list[BindingResult], int] - 分页
      方法5: mark_released(binding_id, trace_id) -> None - 标记已释放
    [来源标注] [DD-001:DS-002 + MD-MCP-V1.0-20260602#M-B03]
    """

    @abstractmethod
    async def exists(self, ws_id: UUID, mcp_id: UUID) -> bool:
        """检查绑定是否存在.

        [函数名] exists
        [职责] 用于 bind 时的冲突检测
        [参数说明]
          参数1: ws_id UUID 必填
          参数2: mcp_id UUID 必填
        [返回值]
          类型: bool
        [并发安全] SELECT 无锁
        [性能约束] PG UNIQUE 索引命中
        [来源标注] [DD-001:DS-002 + MD-MCP-V1.0-20260602#M-B03]
        """
        raise NotImplementedError

    @abstractmethod
    async def add(
        self,
        ws_id: UUID,
        mcp_id: UUID,
        mapping: Mapping,
        config_path: Path,
        pid: int,
        trace_id: str,
    ) -> UUID:
        """插入 binding 记录.

        [函数名] add
        [职责] 持久化
        [参数说明]
          参数1: ws_id UUID 必填
          参数2: mcp_id UUID 必填
          参数3: mapping Mapping 必填
          参数4: config_path Path 必填
          参数5: pid int 必填
          参数6: trace_id str 必填
        [返回值]
          类型: UUID
          描述: 新插入的 binding_id
        [错误码]
          错误码1: DB_INTEGRITY_VIOLATION 409 - UNIQUE 冲突
        [并发安全] INSERT（依赖 UNIQUE 约束）
        [幂等性] 否
        [性能约束] P95 ≤ 30ms
        [来源标注] [DD-001:DS-002]
        """
        raise NotImplementedError

    @abstractmethod
    async def get(self, binding_id: UUID) -> BindingResult | None:
        """查询单条 binding.

        [函数名] get
        [职责] 按 ID 查询
        [参数说明]
          参数1: binding_id UUID 必填
        [返回值]
          类型: BindingResult | None
        [来源标注] [DD-001:DS-002]
        """
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        ws_id: UUID,
        page: int,
        size: int,
        trace_id: str,
    ) -> tuple[list[BindingResult], int]:
        """分页查询.

        [函数名] list
        [职责] 按 ws_id 列出 binding
        [参数说明]
          参数1: ws_id UUID 必填
          参数2: page int 必填
          参数3: size int 必填
          参数4: trace_id str 必填
        [返回值]
          类型: tuple[list[BindingResult], int]
        [来源标注] [DD-001:DS-002]
        """
        raise NotImplementedError

    @abstractmethod
    async def mark_released(self, binding_id: UUID, trace_id: str) -> None:
        """标记 binding 已释放.

        [函数名] mark_released
        [职责] 软状态变更 state=Active → Released
        [参数说明]
          参数1: binding_id UUID 必填
          参数2: trace_id str 必填
        [来源标注] [DD-001:DS-002]
        """
        raise NotImplementedError


__all__ = ["BindingRepository"]
