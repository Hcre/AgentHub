# AgentHub 架构红线

> 版本: v2.1 | 违反任一条 = 方案打回

## AR-01：5 层依赖倒置

```
L5 → L4 → L3 → L2 ← L1
              ↑
              └── L1 实现 L2 定义的接口
```

- L2（Domain）不 import L1/L3/L4/L5 任何模块
- L1（Infrastructure）实现 L2 定义的 `AgentRepository` / `LLMAdapter` / `TaskQueue` 接口
- L3（Application）通过依赖注入组装 L1 实现 + L2 领域对象

## AR-02：新 Agent 系统只加 Adapter

新增 Agent 系统（如 Claude/Codex/TRAE），只需：
1. 在 `backend/app/adapters/` 创建 `xxx_adapter.py`
2. 继承 `base.LLMAdapter`，实现 `chat()` / `stream_chat()` / `get_capabilities()`
3. adapter 内部通过 `provider + model + api_key + base_url` 配置底层 LLM

禁止修改 `domain/` 中任何代码来适配新系统。

## AR-03：Harness 不含 LLM 调用

`backend/app/domain/task_engine.py` 中所有逻辑必须是确定性 Python 代码。
Coordinator Agent（LLM）的输出是结构化 JSON，Harness 接收后校验并执行。
Harness 有权否决 Agent 的决策（环检测/预算/负载）。

## AR-04：Agent 间不直接通信

Agent A 不能直接给 Agent B 发消息。必须通过：
1. Blackboard（共享制品读写）
2. Coordinator（变更提案 → 审查 → 广播）

## AR-05：Task Engine 状态变更必须走事件溯源

禁止直接修改 `tasks.status`。所有变更必须：
1. Guard Functions 校验合法性
2. 写入 `task_events` 事件日志（只追加，不可变）
3. 幂等键防重

## AR-06：Agent 系统与模型解耦

- `agent_system`（claude/codex/trae）决定用哪个运行时
- `provider + model + api_key + base_url` 决定底层 LLM
- 两者独立选择，不允许在代码中硬编码 system→model 的映射
