"""Task Engine：FSM（状态机）+ Harness（编排）+ Coordinator（LLM 分解）。

边界（见 04_协调者黑板模式对比分析.md）：
- Coordinator = LLM，负责"判断"（任务分解、异常诊断、Agent 推荐）。
- Harness = 纯代码，负责"执行"（FSM 流转、Guard 校验、DAG 编译、预算管控）。
"""

from app.domain.task_engine.fsm import VALID_TRANSITIONS, TaskFSM

__all__ = ["VALID_TRANSITIONS", "TaskFSM"]
