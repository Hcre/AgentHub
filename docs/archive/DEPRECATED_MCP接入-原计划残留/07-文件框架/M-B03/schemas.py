"""M-B03 Binding Engine DTO / Pydantic Schema.

[文件路径] src/agenthub/application/binding/schemas.py
[文件职责] 定义 Binding Engine 对外 DTO（frozen 模式）
[所属模块] M-B03
[关联设计规范] MD-MCP-V1.0-20260602#M-B03
[功能描述]
  功能1: BindForm 绑定入参
  功能2: BindingResult 绑定结果
  功能3: Mapping 类型别名（dict[str, str]）
[输入输出]
  输入: HTTP request body / path
  输出: HTTP response body
[依赖关系]
  依赖文件: pydantic
  被依赖文件: agenthub.application.binding.controllers、services
[注意事项]
  注意1: 所有 Schema 必须 frozen=True（不可变 Value Object）
  注意2: 字段必须有 Field 描述
  注意3: UUID 类型统一使用 pydantic UUID4
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版 Schema
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Mapping = dict[str, str]
"""Mapping 类型别名：alias → server URL."""


class BindForm(BaseModel):
    """绑定入参.

    [类名] BindForm
    [职责] 接收 POST /bindings 请求体
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03 + API-120
    [属性]
      属性1: workspace_id UUID 必填
      属性2: mcp_id UUID 必填
      属性3: mapping Mapping 可选 默认 None（使用 1:1 默认策略）
      属性4: mapping_kind str 可选 默认 "default"
    [来源标注] [DD-001:API-120]
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: UUID = Field(..., description="工作区 ID")
    mcp_id: UUID = Field(..., description="MCP ID")
    mapping: Mapping | None = Field(default=None, description="别名映射；缺省时使用 1:1")
    mapping_kind: str = Field(
        default="default", description="策略类型 default/custom", pattern="^(default|custom)$"
    )


class BindingResult(BaseModel):
    """绑定结果.

    [类名] BindingResult
    [职责] 绑定成功的返回结构
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03
    [属性]
      属性1: binding_id UUID 可选
      属性2: state str 必填 Active | Released
      属性3: config_path Path 必填
      属性4: pid int 必填
      属性5: ws_id UUID 必填
      属性6: mcp_id UUID 必填
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    binding_id: UUID | None = Field(default=None, description="绑定 ID")
    state: str = Field(..., description="Active | Released", pattern="^(Active|Released|Pending)$")
    config_path: Path = Field(..., description="mcp-config 文件路径")
    pid: int = Field(..., ge=-1, description="进程 PID（-1 表示未 spawn）")
    ws_id: UUID = Field(..., description="工作区 ID")
    mcp_id: UUID = Field(..., description="MCP ID")

    def to_dict(self) -> dict[str, Any]:
        """转 dict.

        [函数名] to_dict
        [职责] 序列化（Path → str）
        [返回值]
          类型: dict[str, Any]
        [来源标注] [DD-M推断:典型响应序列化]
        """
        return {
            "binding_id": str(self.binding_id) if self.binding_id else None,
            "state": self.state,
            "config_path": str(self.config_path),
            "pid": self.pid,
            "ws_id": str(self.ws_id),
            "mcp_id": str(self.mcp_id),
        }


__all__ = ["BindForm", "BindingResult", "Mapping"]
