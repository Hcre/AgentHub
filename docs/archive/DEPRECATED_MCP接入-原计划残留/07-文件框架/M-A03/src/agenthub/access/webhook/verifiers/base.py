"""M-A03 HMACVerifier 抽象基类.

[文件路径] src/agenthub/access/webhook/verifiers/base.py
[文件职责] 定义验签器接口与工具函数
[所属模块] M-A03（来自DD-001）
[关联设计规范] MD-M-A03（来自DD-001）
[功能描述]
  功能1: 定义 HMACVerifier ABC（verify 抽象方法）
  功能2: 提供 verify_hmac 工具函数（hmac.compare_digest 抗时序攻击）
[输入输出]
  输入: payload bytes + signature str + secret bytes
  输出: bool 验签结果
[依赖关系]
  依赖文件: 标准库 hmac/hashlib
  被依赖文件: github.py / gitlab.py / bitbucket.py / app.py
[注意事项]
  注意1: 必须使用 hmac.compare_digest，禁止 ==
  注意2: signature 解码失败应返回 False（不抛异常）
  注意3: secret 长度 < 16 字节应启动期 warning
[代码风格] 遵循CS-MCP-V1.0 §1.6/§1.3
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-A03-20260603 - 初始版本
[作者] DD-M-A03-20260603
[来源标注] [DD-001:MD-M-A03]
"""

from __future__ import annotations

import abc
import hashlib
import hmac
from typing import Final

from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    pass

from typing import TYPE_CHECKING  # noqa: E402

log = get_logger(__name__)

SUPPORTED_HASH_ALGO: Final[str] = "sha256"


class HMACVerifier(abc.ABC):
    """HMAC 验签抽象基类.

    [职责] 定义 source-specific 验签器的统一接口
    [关联设计规范] MD-M-A03（来自DD-001）
    [属性]
      属性1: source str 来源系统标识
      属性2: secret bytes 从 Vault 拉取的共享密钥
    [方法列表]
      方法1: verify(payload, signature) -> bool - 抽象验签
    [异常处理]
      异常1: HMACMismatchError - verify 返回 False 时由调用方抛
    [来源标注] [DD-001:MD-M-A03]
    """

    def __init__(self, source: str, secret: bytes) -> None:
        """初始化验签器.

        [函数名] __init__
        [职责] 保存 source 与 secret
        [参数说明]
          参数1: source str 必填 github|gitlab|bitbucket
          参数2: secret bytes 必填 Vault 拉取的共享密钥
        [返回值] None
        [前置条件] secret 长度 ≥ 16 字节
        [并发安全] 不可变对象，线程安全
        [来源标注] [DD-001:MD-M-A03]
        """
        ...

    @abc.abstractmethod
    def verify(self, payload: bytes, signature: str) -> bool:
        """验签抽象方法.

        [函数名] verify
        [职责] 比对 payload 哈希与 signature
        [参数说明]
          参数1: payload bytes 必填 原始请求体
          参数2: signature str 必填 来源系统签名头
        [返回值]
          类型: bool
          描述: True=验签通过，False=验签失败
          特殊值: 失败时由调用方（app.handle）抛 HMACMismatchError
        [前置条件] signature 已 hex decode 校验格式
        [后置条件] 不写任何状态
        [并发安全] 无状态；线程安全
        [幂等性] 是；同输入同输出
        [性能约束] < 5ms
        [来源标注] [DD-001:MD-M-A03]
        """
        ...


def verify_hmac(payload: bytes, signature: str, secret: bytes) -> bool:
    """通用 HMAC-SHA256 验签函数.

    [函数名] verify_hmac
    [职责] 计算 payload 的 HMAC 并与 signature 常量时间比对
    [参数说明]
      参数1: payload bytes 必填 原始请求体
      参数2: signature str 必填 期望的 hex 编码签名
      参数3: secret bytes 必填 共享密钥
    [返回值]
      类型: bool
      描述: True=一致，False=不一致或格式错误
    [前置条件] signature 为 hex 字符串
    [后置条件] 无副作用
    [并发安全] 纯函数；线程安全
    [幂等性] 是
    [性能约束] < 5ms（O(n) 哈希）
    [示例]
      ```
      ok = verify_hmac(b'{"event":"push"}', header_sig, vault_secret)
      ```
    [来源标注] [DD-001:MD-M-A03]
    """
    ...
