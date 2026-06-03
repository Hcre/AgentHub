"""M-C05 Network ACL 控制器.

[文件路径] src/agenthub/infrastructure/network_acl/controller.py
[文件职责] workspace 级 ACL 规则应用入口（FastAPI router + 业务编排）
[所属模块] M-C05（来自DD-001）
[关联设计规范] FS-014 / MD-MCP-V1.0-20260602#M-C05
[功能描述]
  功能1: 提供 POST /acl/apply 接口（实现 IC-012）
  功能2: 选择 backend（iptables/docker_network/ipset）并串行化 per-workspace
  功能3: 处理 ACL_CONFLICT / ACL_BACKEND_UNAVAILABLE 异常
[输入输出]
  输入: workspace_id (UUID), rules (list[ACLRule])
  输出: applied_rule_ids (list[UUID])
[依赖关系]
  依赖文件: ./backends/base.py, ./backends/iptables.py,
            ./backends/docker_network.py, ./backends/ipset.py,
            agenthub.core.exceptions
  被依赖文件: agenthub.application.binding（M-B03 调用以注入 per-ws 规则）
[注意事项]
  注意1: per-workspace 串行化（PG row-lock，[DD-001:IC-012]）
  注意2: rule_hash 重复时直接跳过（幂等，[DD-001:IC-012]）
  注意3: 切换 backend 时需告警并保留旧规则直到新规则应用成功
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C05 - 初始框架
[作者] DD-M-C05-2026-06-03
[来源标注] [DD-001:FS-014/MD-MCP-V1.0-20260602#M-C05/IC-012]
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from agenthub.core.exceptions import AgentHubError
from agenthub.core.logging import get_logger

from agenthub.infrastructure.network_acl.backends.base import ACLBackend

if TYPE_CHECKING:
    from agenthub.infrastructure.network_acl.backends.iptables import IptablesBackend
    from agenthub.infrastructure.network_acl.backends.docker_network import DockerNetworkBackend
    from agenthub.infrastructure.network_acl.backends.ipset import IpsetBackend


log = get_logger(__name__)


# === Pydantic DTO（仅注释，DD-S 据此生成代码） ===

class ACLRule(BaseModel):
    """ACL 规则模型.

    [类名] ACLRule
    [职责] 表示单条网络 ACL 规则
    [关联设计规范] MD-MCP-V1.0-20260602#M-C05
    [属性]
      属性1: rule_id UUID 规则唯一标识（哈希派生）
      属性2: direction enum[ingress|egress] 方向
      属性3: protocol enum[tcp|udp|icmp|any] 协议
      属性4: port int 端口（any 时为 0）
      属性5: cidr str 源/目标 CIDR
      属性6: action enum[allow|deny] 动作
      属性7: workspace_id UUID 所属工作区
    [方法列表]
      方法1: rule_hash() → str - 计算规则哈希用于幂等键
    [状态机] Drafted → Applied → Revoked
    [异常处理]
      异常1: ValidationError - 字段非法
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
    """
    rule_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    direction: str = Field(..., pattern="^(ingress|egress)$")
    protocol: str = Field(..., pattern="^(tcp|udp|icmp|any)$")
    port: int = Field(0, ge=0, le=65535)
    cidr: str = Field(..., min_length=1)
    action: str = Field(..., pattern="^(allow|deny)$")
    workspace_id: uuid.UUID


class ApplyRequest(BaseModel):
    """apply 接口入参 DTO.

    [类名] ApplyRequest
    [职责] POST /acl/apply 的请求体
    [来源标注] [DD-001:IC-012]
    """
    workspace_id: uuid.UUID
    rules: list[ACLRule]


class ApplyResponse(BaseModel):
    """apply 接口出参 DTO.

    [类名] ApplyResponse
    [职责] POST /acl/apply 的响应体
    [来源标注] [DD-001:IC-012]
    """
    applied_rule_ids: list[uuid.UUID]


# === 业务类（仅注释，DD-S 据此生成代码） ===

class ACLController:
    """ACL 控制器（FastAPI router 容器 + 业务编排）.

    [类名] ACLController
    [职责] 暴露 HTTP API 并编排 backend 应用/撤销规则
    [关联设计规范] MD-MCP-V1.0-20260602#M-C05
    [属性]
      属性1: router APIRouter FastAPI 路由
      属性2: _backends dict[str, ACLBackend] 可用 backend 映射（name → 实例）
      属性3: _active_backend str 当前激活 backend 名
    [方法列表]
      方法1: apply(workspace_id, rules) → list[UUID]
      方法2: revoke(rule_id) → None
      方法3: _select_backend(workspace_id) → ACLBackend
    [状态机] 无业务状态（HTTP 层无状态）
    [异常处理]
      异常1: ACLBackendUnavailable 503 - 切换备选 backend
      异常2: ACLConflict 409 - 规则冲突
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05/IC-012]
    """

    def __init__(self) -> None:
        """初始化控制器（注入 backend 实例）.

        [函数名] __init__
        [职责] 构造 FastAPI router 与 backend 映射
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        # [DD-M推断:FS-014 未列构造函数签名，参考 M-B03 BindingController 风格]
        ...

    async def apply(self, workspace_id: uuid.UUID, rules: list[ACLRule]) -> list[uuid.UUID]:
        """应用 ACL 规则到指定 workspace.

        [函数名] apply
        [职责] 串行化 per-workspace + 幂等检查 + 调用 backend
        [关联接口契约] IC-012（来自DD-001）
        [参数说明]
          参数1: workspace_id UUID 必填 工作区 ID
          参数2: rules list[ACLRule] 必填 待应用规则列表（非空）
        [返回值]
          类型: list[UUID]
          描述: 成功应用的规则 ID 列表
          特殊值: 空列表表示全部幂等跳过
        [错误码]
          错误码1: ACL_BACKEND_UNAVAILABLE 503 后端不可用
          错误码2: ACL_CONFLICT 409 规则冲突
        [前置条件] 调用方具备 admin 权限（U-04）
        [后置条件] 规则已写入 backend 且 PG acl_rules 表入库
        [并发安全] per-workspace 串行（PG row-lock，[DD-001:IC-012]）
        [幂等性]
          是否幂等: 是
          幂等键来源: rule_hash
          重复处理: 跳过已存在规则
        [性能约束] P95 ≤ 1s
        [来源标注] [DD-001:IC-012/MD-MCP-V1.0-20260602#M-C05]
        """
        ...

    async def revoke(self, rule_id: uuid.UUID) -> None:
        """撤销单条 ACL 规则.

        [函数名] revoke
        [职责] 从所有 backend 移除规则
        [关联接口契约] IC-012 关联子操作
        [参数说明]
          参数1: rule_id UUID 必填 规则 ID
        [返回值]
          类型: None
          描述: 无返回值
        [错误码]
          错误码1: ACL_NOT_FOUND 404 规则不存在
        [前置条件] 规则处于 Applied 状态
        [后置条件] 规则从 backend 移除且状态转 Revoked
        [并发安全] per-workspace 串行
        [幂等性] 否（重复 revoke 返回 404）
        [性能约束] P95 ≤ 500ms
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        ...

    def _select_backend(self, workspace_id: uuid.UUID) -> ACLBackend:
        """选择 backend（Strategy 选择）.

        [函数名] _select_backend
        [职责] 根据 OS / 容器环境选择 iptables / docker_network / ipset
        [来源标注] [DD-M推断:参考 M-C01 SandboxFactory 探测模式]
        """
        ...


# === 异常定义（仅注释，DD-S 据此生成代码） ===

class ACLBackendUnavailable(AgentHubError):
    """backend 不可用异常（503）.

    [类名] ACLBackendUnavailable
    [职责] 表示所有 backend 均不可用
    [来源标注] [DD-001:IC-012]
    """
    http_status: int = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code: str = "ACL_BACKEND_UNAVAILABLE"


class ACLConflict(AgentHubError):
    """规则冲突异常（409）.

    [类名] ACLConflict
    [职责] 表示规则与现有规则冲突
    [来源标注] [DD-001:IC-012]
    """
    http_status: int = status.HTTP_409_CONFLICT
    error_code: str = "ACL_CONFLICT"


# === FastAPI router 注册（仅注释，DD-S 据此生成代码） ===

router = APIRouter(prefix="/acl", tags=["network-acl"])


# [DD-M推断:FS-014 未明确 router 路径前缀，参考 M-A01 /acl 命名约定]
