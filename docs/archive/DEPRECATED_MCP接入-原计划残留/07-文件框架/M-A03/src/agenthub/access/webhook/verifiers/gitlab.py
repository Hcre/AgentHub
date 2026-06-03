"""M-A03 GitLabVerifier 验签器.

[文件路径] src/agenthub/access/webhook/verifiers/gitlab.py
[文件职责] 实现 GitLab 风格 X-Gitlab-Token 等值比对验签
[所属模块] M-A03（来自DD-001）
[关联设计规范] MD-M-A03 / IC-003（来自DD-001）
[功能描述]
  功能1: 解析 X-Gitlab-Token 头（明文共享 token）
  功能2: 使用 hmac.compare_digest 做常量时间比对
[输入输出]
  输入: payload bytes + token str（X-Gitlab-Token 头值）
  输出: bool 验签结果
[依赖关系]
  依赖文件: base.py
  被依赖文件: app.py (verifiers["gitlab"])
[注意事项]
  注意1: GitLab 默认 token 模式（非 HMAC），这里采用 SEC-006 推荐的常量时间比对
  注意2: 失败时返回 False，不抛异常
[代码风格] 遵循CS-MCP-V1.0
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本
[作者] DD-M-A03-20260603
[来源标注] [DD-001:MD-M-A03 + IC-003 + SEC-006]
"""

from __future__ import annotations

import hmac

from agenthub.access.webhook.verifiers.base import HMACVerifier
from agenthub.core.logging import get_logger

log = get_logger(__name__)


class GitLabVerifier(HMACVerifier):
    """GitLab webhook 验签器.

    [职责] 验签 X-Gitlab-Token 等值
    [关联设计规范] MD-M-A03（来自DD-001）
    [属性]
      属性1: source str 固定 "gitlab"
      属性2: secret bytes 共享 token
    [方法列表]
      方法1: verify(payload, signature) -> bool - 验签入口
    [来源标注] [DD-001:MD-M-A03 + SEC-006]
    """

    def verify(self, payload: bytes, signature: str) -> bool:
        """GitLab X-Gitlab-Token 等值验签.

        [函数名] verify
        [职责] 常量时间比对 token
        [参数说明]
          参数1: payload bytes 必填 原始请求体（仅用于日志，不参与计算）
          参数2: signature str 必填 X-Gitlab-Token 头值
        [返回值]
          类型: bool
          描述: True=通过；False=不一致
        [错误码] 失败由调用方抛 HMACMismatchError（401）
        [前置条件] secret 来自 Vault
        [后置条件] 无
        [并发安全] 无状态；线程安全
        [幂等性] 是
        [性能约束] < 1ms
        [来源标注] [DD-001:MD-M-A03 + SEC-006]
        """
        ...
