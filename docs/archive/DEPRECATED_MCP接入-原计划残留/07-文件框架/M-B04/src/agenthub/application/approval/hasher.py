"""M-B04 Approval Engine — 系统级公共参数哈希器（ADR-006 单一来源）.

[文件路径] src/agenthub/application/approval/hasher.py
[文件职责] 提供全系统唯一的 args→hash 转换函数；纯函数，无状态，无 IO
[所属模块] M-B04
[关联设计规范] FS-008 / MD:M-B04 类设计 #3 / ADR-006
[关联接口契约] IC-005 (作为 allowlist 幂等键的组成部分)
[功能描述]
  功能1: compute_args_hash(args) → 64 字符 SHA256 hex
  功能2: 保证 dict key 顺序无关性（sorted_json）
  功能3: 提供 verify_hash(args, expected) → bool（hash 一致性校验）
[输入输出]
  输入: args: dict[str, object]
  输出: SHA256 hex 字符串（64 字符）
[依赖关系]
  依赖文件: 仅依赖标准库 hashlib + json
  被依赖文件: services.py / allowlist.py / 其他模块（如 M-B05 secret 流程，通过 __init__ 导出复用）
[注意事项]
  注意1: 此为 ADR-006 指定的系统级单一哈希实现，禁止其他模块重复实现
  注意2: args 必须可 JSON 序列化；含 datetime/UUID/bytes 等需调用方先转换
  注意3: 算法变更必须升版本（hash_v2）并保留 v1 兼容，避免 allowlist 失效
  注意4: 必须使用 sort_keys=True + separators=(",",":") 消除空白差异
[代码风格] 遵循 CS §1.3 (类型注解) + §1.9 (@pure 装饰器)
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:ADR-006 + MD:M-B04 类设计 #3 + CS §1.9]
"""

from __future__ import annotations

# 实际 import 由 DD-S 阶段补全（hashlib / json / agenthub.core.pure）

# ---------------------------------------------------------------------------
# 类注释 — ArgsHasher
# ---------------------------------------------------------------------------
# [类名] ArgsHasher
# [职责] 系统级参数哈希纯函数容器（ADR-006 单一来源）
# [关联设计规范] MD:M-B04 类设计 #3 + ADR-006
# [属性] 无（全部为 @staticmethod）
# [方法列表]
#   @staticmethod
#   compute_args_hash(args: dict) → str
#       - 系统级统一哈希；sorted_json + SHA256；64 字符 hex
#   @staticmethod
#   verify_hash(args: dict, expected: str) → bool
#       - 用于 services.decide 中 HashMismatch 检测
#   @staticmethod
#   _canonical_json(args: dict) → str
#       - 内部辅助：sort_keys=True, separators=(",",":")（私有，_前缀）
# [状态机] 无
# [异常处理]
#   ValueError → args 含不可 JSON 序列化对象（datetime/UUID/bytes 等需调用方先转）
#   TypeError  → args 不是 dict
# [来源标注] [DD-001:MD:M-B04 + ADR-006]


# ---------------------------------------------------------------------------
# 函数注释 — compute_args_hash
# ---------------------------------------------------------------------------
# [函数名] compute_args_hash
# [职责] 计算工具调用参数的 SHA256 哈希（系统级唯一实现）
# [关联接口契约] IC-005 (allowlist 幂等键)
# [参数说明]
#   args: dict[str, object]  必填  工具调用参数
#         校验:
#           - 必须为 dict（不接受 list/str/None）
#           - 所有值必须可 JSON 序列化（int/float/str/bool/None/dict/list 嵌套）
#           - 序列化后 UTF-8 字节流 ≤ 16KB（IC-005 入参约束）
# [返回值]
#   类型: str
#   描述: SHA256 hex 字符串，长度固定 64
#   特殊值: 空 dict {} → e3b0c442... (SHA256 of "{}")
# [错误码]
#   ValueError - args 含不可序列化对象 - 调用方先转换为基础类型
#   TypeError  - args 非 dict           - 修正调用
# [前置条件] args 为合法 dict
# [后置条件] 不修改 args（纯函数）
# [并发安全] 线程安全（无状态，无 IO）
# [幂等性] 是；same input → same output；永久；返回相同
# [性能约束] < 1ms (典型 1KB args)；< 5ms (16KB 上限)
# [示例]
#   >>> ArgsHasher.compute_args_hash({"a": 1, "b": 2})
#   "..."  # 64 字符 hex
#   >>> ArgsHasher.compute_args_hash({"b": 2, "a": 1})
#   "..."  # 同上（顺序无关）
# [来源标注] [DD-001:ADR-006 + MD:M-B04 函数签名 #3]


# ---------------------------------------------------------------------------
# 函数注释 — verify_hash
# ---------------------------------------------------------------------------
# [函数名] verify_hash
# [职责] 一致性校验（services.decide 中检测 HashMismatch 用）
# [关联接口契约] IC-005 错误码 APPROVAL_HASH_MISMATCH
# [参数说明]
#   args:     dict  必填  当前参数
#   expected: str   必填  期望哈希（从 inbox_queue.args_hash 读取）
# [返回值]
#   类型: bool
#   描述: True = 一致 / False = 不一致（触发 ERROR 告警）
# [错误码] 同 compute_args_hash
# [并发安全] 线程安全
# [幂等性] 是
# [性能约束] < 1ms
# [示例]
#   if not ArgsHasher.verify_hash(args, stored_hash):
#       log.error("approval_hash_mismatch", ...)
#       raise ApprovalHashMismatch()
# [来源标注] [DD-M-B04 推断: MD 提及 HashMismatch 但未给函数签名；按 ADR-006 单一来源原则集中放置]
