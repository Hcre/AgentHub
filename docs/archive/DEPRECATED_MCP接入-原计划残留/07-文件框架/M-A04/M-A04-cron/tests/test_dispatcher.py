"""
[文件路径] src/agenthub/access/cron/tests/test_dispatcher.py
[文件职责] JobDispatcher 单元测试（arq enqueue spy）
[所属模块] M-A04（来自DD-001）
[关联设计规范] MD-MCP-V1.0-20260602.md#M-A04 测试策略
[功能描述]
  功能1: 验证 dispatch / dispatch_with_retry 路径
  功能2: 模拟 arq 失败 → 重试 → 最终成功
[输入输出] 输入: arq spy fixture；输出: pytest 报告
[依赖关系]
  依赖文件: dispatcher.py / pytest / pytest-mock
  被依赖文件: 无
[注意事项] 注意1: arq.enqueue_job 用 pytest-mock spy
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.7
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-04 - 初始框架
[作者] DD-M-04-20260603
[来源标注] [DD-001:MD-MCP-V1.0-20260602.md#M-A04 测试策略 + EX-007]
"""
from __future__ import annotations

import pytest

# [测试场景1: 正常派发]
# 输入: 合法 job_name/payload/trace_id
# 断言: 返回 task_id（UUID 格式）；arq.enqueue_job 被调用 1 次
# Mock: ArqRedis.enqueue_job spy

# [测试场景2: 派发失败重试 1 次后成功]
# 输入: arq.enqueue_job 第一次抛 ConnectionError
# 断言: 重试 1 次后成功；总调用次数=2
# Mock: ArqRedis.enqueue_job side_effect=[ConnectionError, "task_id"]

# [测试场景3: 派发重试 3 次仍失败]
# 输入: arq.enqueue_job 始终抛 ConnectionError
# 断言: 抛 DispatchError；总调用次数=3；总耗时约 1+2+4=7s（用 freezegun 加速）
# Mock: ArqRedis.enqueue_job side_effect=ConnectionError × 3

# [测试场景4: payload 不可序列化]
# 输入: payload 包含 set 对象
# 断言: 立即抛 SerializationError（不重试）
# Mock: ArqRedis.enqueue_job

# [测试场景5: 派发携带 trace_id]
# 输入: trace_id="01HX..."
# 断言: arq.enqueue_job 调用时 task_id 含 trace_id 前缀
# Mock: ArqRedis.enqueue_job
