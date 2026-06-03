"""Market 模块 DTO / Schema 定义.

[文件路径] src/agenthub/application/market/schemas.py
[文件职责] Pydantic BaseModel；ListFilter / Page / MCPServerDTO / MCPServerDetail
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-MCP-V1.0-20260602#FS-005
[功能描述]
  功能1: 请求体 / 响应体强类型（FastAPI 自动校验 + OpenAPI 文档）
  功能2: ORM ↔ DTO 转换由 Repository/Service 层负责（DTO 不依赖 ORM）
[输入输出]
  输入: HTTP 请求体 / ORM 模型
  输出: JSON / DTO
[依赖关系]
  依赖文件: 无业务依赖（仅 pydantic 标准库）
  被依赖文件: controllers / services / repositories / decorators
[注意事项]
  注意1: 所有 DTO 必须 frozen（model_config frozen=True），避免业务侧意外修改
  注意2: 字段命名严格 snake_case；序列化时使用 alias（[CS-001 §2.4]）
  注意3: 时间字段统一 ISO8601（[DD-001:API-100]）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.3（类型注解 100% 覆盖）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-B01 - 初版 DTO
[作者] DD-M-B01-20260602
[来源标注] [DD-001:FS-005/MD-MCP#M-B01/IC-MCP#API-100]
"""
from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ListFilter(BaseModel):
    """MCP Server 列表过滤条件.

    [类名] ListFilter
    [职责] 列表查询入参
    [关联设计规范] MD-MCP-V1.0-20260602#M-B01
    [属性]
      属性1: tags list[str] 标签过滤
      属性2: page int 页码 ≥ 1
      属性3: size int 每页大小 1-100
      属性4: sort_by enum[created_at|updated_at|name] 排序字段
      属性5: order enum[asc|desc] 排序方向
    [方法列表] 无（纯数据）
    [异常处理] Pydantic 自动校验 → 422
    [来源标注] [DD-001:IC-MCP#API-100]
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    tags: list[str] = Field(default_factory=list, max_length=20)
    page: int = Field(default=1, ge=1, le=1000)
    size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at", pattern="^(created_at|updated_at|name)$")
    order: str = Field(default="desc", pattern="^(asc|desc)$")


class MCPServerDTO(BaseModel):
    """MCP Server 列表项 DTO.

    [类名] MCPServerDTO
    [职责] 列表项视图
    [属性]
      属性1: id UUID
      属性2: name str ≤ 128
      属性3: description str ≤ 512
      属性4: tags list[str]
      属性5: author str
      属性6: created_at datetime ISO8601
    [来源标注] [DD-001:MD-MCP#M-B01]
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    id: UUID
    name: str = Field(max_length=128)
    description: str = Field(max_length=512)
    tags: list[str]
    author: str
    created_at: datetime


class MCPServerDetail(BaseModel):
    """MCP Server 详情 DTO.

    [类名] MCPServerDetail
    [职责] 单个 Server 完整详情
    [属性]
      属性1: id UUID
      属性2: name str
      属性3: description str
      属性4: manifest_json dict
      属性5: tags list[str]
      属性6: author str
      属性7: k4_score int 1-10
      属性8: version str semver
      属性9: created_at / updated_at datetime
    [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    id: UUID
    name: str
    description: str
    manifest_json: dict[str, object]
    tags: list[str]
    author: str
    k4_score: int = Field(ge=1, le=10)
    version: str
    created_at: datetime
    updated_at: datetime


class Page(BaseModel, Generic[T]):
    """通用分页结果.

    [类名] Page
    [职责] 包装分页响应
    [属性]
      属性1: items list[T]
      属性2: total int
      属性3: page int
      属性4: size int
    [来源标注] [DD-M推断:复用 M-D01 Page 规范，节省设计]
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    size: int = Field(ge=1)
