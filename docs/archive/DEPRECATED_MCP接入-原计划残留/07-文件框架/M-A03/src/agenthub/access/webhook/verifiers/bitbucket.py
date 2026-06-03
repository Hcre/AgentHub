"""M-A03 BitbucketVerifier 验签器.

[文件路径] src/agenthub/access/webhook/verifiers/bitbucket.py
[文件职责] 实现 Bitbucket 风格 HMAC-SHA256 验签
[所属模块] M-A03（来自DD-001）
[关联设计规范] MD-M-A03 / IC-003（来自DD-001）
[功能描述]
  功能1: 解析 X-Hub-Signature 头（格式 sha256=<hex>）
  功能2: 复用 base.verify_hmac 常量时间比对
[输入输出]
  输入: payload bytes + signature str
  输出: bool 验签结果
[依赖关系]
  依赖文件: base.py
  被依赖文件: app.py (verifiers["bitbucket"])
[注意事项]
  注意1: Bitbucket 旧版 X-Hub-Signature（无 256 后缀）
  注意2: 头部缺失前缀返回 False
[代码风格] 遵循CS-MCP-V1.0
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本
[作者] DD-M-A03-20260603
[来源标注] [DD-001:MD-M-A03 + IC-003]
"""

from __future__ import annotations

from agenthub.access.webhook.verifiers.base import HMACVerifier, verify_hmac
from agenthub.core.logging import get_logger

log = get_logger(__name__)


class BitbucketVerifier(HMACVerifier):
    """Bitbucket webhook 验签器.

    [职责] 验签 X-Hub-Signature = "sha256=<hex>"
    [关联设计规范] MD-M-A03（来自DD-001）
    [属性]
      属性1: source str 固定 "bitbucket"
      属性2: secret bytes 共享密钥
    [方法列表]
      方法1: verify(payload, signature) -> bool - 验签入口
    [来源标注] [DD-001:MD-M-A03]
    """

    def verify(self, payload: bytes, signature: str) -> bool:
        """Bitbucket HMAC-SHA256 验签.

        [函数名] verify
        [职责] 解析 "sha256=<hex>" 头并常量时间比对
        [参数说明]
          参数1: payload bytes 必填 原始请求体
          参数2: signature str 必填 X-Hub-Signature 头值
        [返回值]
          类型: bool
          描述: True=通过；False=格式错误或签名不一致
        [错误码] 失败由调用方抛 HMACMismatchError（401）
        [前置条件] signature 含 "sha256=" 前缀
        [后置条件] 无
        [并发安全] 无状态；线程安全
        [幂等性] 是
        [性能约束] < 5ms
        [来源标注] [DD-001:MD-M-A03]
        """
        ...
