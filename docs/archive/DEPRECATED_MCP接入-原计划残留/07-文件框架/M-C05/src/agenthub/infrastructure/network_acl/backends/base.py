"""M-C05 Network ACL backend 抽象基类.

[文件路径] src/agenthub/infrastructure/network_acl/backends/base.py
[文件职责] 定义 ACLBackend ABC（Strategy + Adapter 模式核心）
[所属模块] M-C05（来自DD-001）
[关联设计规范] FS-014 / MD-MCP-V1.0-20260602#M-C05
[功能描述]
  功能1: 定义 apply/revoke 抽象接口
  功能2: 提供 backend 健康探测钩子
[输入输出]
  输入: ACLRule 列表 / rule_id
  输出: apply 成功标识 / 异常
[依赖关系]
  依赖文件: ../controller.py（ACLRule 类型）
  被依赖文件: iptables.py / docker_network.py / ipset.py
[注意事项]
  注意1: ABC 子类必须实现 apply/revoke/healthcheck
  注意2: 子类的 subprocess 调用必须 timeout（10s 默认，[CS-001]）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-C05 - 初始框架
[作者] DD-M-C05-2026-06-03
[来源标注] [DD-001:FS-014/MD-MCP-V1.0-20260602#M-C05]
"""
from __future__ import annotations

import abc
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agenthub.infrastructure.network_acl.controller import ACLRule


class ACLBackend(abc.ABC):
    """ACL backend 抽象基类.

    [类名] ACLBackend
    [职责] 定义三后端统一接口
    [关联设计规范] MD-MCP-V1.0-20260602#M-C05
    [属性]
      属性1: name str backend 名（iptables/docker_network/ipset）
    [方法列表]
      方法1: apply(rules) → list[UUID] - 应用规则
      方法2: revoke(rule_id) → None - 撤销规则
      方法3: healthcheck() → bool - 健康探测
    [状态机] 无
    [异常处理]
      异常1: ACLBackendUnavailable - subprocess 失败或权限不足
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
    """

    name: str

    @abc.abstractmethod
    async def apply(self, rules: list[ACLRule]) -> list[uuid.UUID]:
        """应用规则到 backend.

        [函数名] apply
        [职责] 将规则写入具体 backend（iptables/ipset/Docker network）
        [关联接口契约] IC-012 后端实现
        [参数说明]
          参数1: rules list[ACLRule] 必填 待应用规则
        [返回值]
          类型: list[UUID]
          描述: 已应用规则 ID 列表
        [错误码]
          错误码1: ACLBackendUnavailable 503 backend 失败
        [前置条件] backend 健康（healthcheck 通过）
        [后置条件] 规则在 OS / 容器层生效
        [并发安全] 子类负责（建议 per-workspace 串行）
        [幂等性] 是（rule_hash 去重）
        [性能约束] P95 ≤ 1s / 100 rules
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        ...

    @abc.abstractmethod
    async def revoke(self, rule_id: uuid.UUID) -> None:
        """从 backend 撤销单条规则.

        [函数名] revoke
        [职责] 按 rule_id 从 backend 移除
        [参数说明]
          参数1: rule_id UUID 必填 规则 ID
        [返回值]
          类型: None
        [错误码]
          错误码1: ACL_NOT_FOUND 404 规则不存在
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        ...

    @abc.abstractmethod
    async def healthcheck(self) -> bool:
        """backend 健康探测.

        [函数名] healthcheck
        [职责] 子类探测命令是否可用 / 权限是否足够
        [返回值]
          类型: bool
          描述: True=健康 / False=不可用
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-C05]
        """
        ...
