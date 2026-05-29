# 架构设计规范 — AgentHub

> **本规范是 [ai-workflow 第一步·编写计划](ai-workflow_AI协作开发流程/03-第一步_编写计划.md) 的细化**，把「技术选型 / 架构设计」环节展开成可执行标准，并作为 [第二步 §2.3 审查](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md)「架构层面」的判据。
>
> AgentHub 是 IM 聊天式多 Agent 协作平台（FastAPI + React + PostgreSQL + Redis），采用 **5 层洋葱架构**与依赖倒置；LLM 接入采取 **SDK/CLI 双轨制**（CLI 优先）。任何架构决策与本规范红线冲突即打回。

---

## 一、红线（必守 · 方案审查命中任一条即打回）

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **AR-01** | **5 层洋葱单向依赖**：`L5 → L4 → L3 → L2 ← L1`。L2 不 import L1/L3/L4/L5；L1 实现 L2 接口 | `import-linter` layers 契约（见 §二） |
| **AR-02** | **新 Agent 系统只加 Adapter**：禁止改 `src/backend/app/domain/` 适配新系统 | `import-linter` forbidden 契约 + CR 审查 |
| **AR-03** | **Harness 不含 LLM 调用**：`src/backend/app/domain/task_engine.py` 全部确定性 Python，LLM 输出为结构化 JSON 由 Harness 校验执行 | grep `httpx/openai/anthropic` in `domain/` |
| **AR-04** | **Agent 间不直接通信**：必须经 Blackboard（共享制品读写）或 Coordinator（提案→审查→广播） | CR 审查 + 调用图扫描 |
| **AR-05** | **Task 状态变更走 FSM + 事件溯源**：禁直接 `task.status = X`，必须经 Guard Functions + FSM + 幂等键 | CR 审查 + 单元测试 |
| **AR-06** | **Agent system 与 model 解耦**：`agent_system`（claude/codex/trae）决定运行时；`provider+model+api_key+base_url` 决定底层 LLM；禁硬编码 system→model 映射 | grep 配置文件 + CR 审查 |

> 密钥硬编码反模式见 [02-代码 CR-10](02-coding_代码编写规范.md)；调用图/孤儿模块见 [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md)。

---

## 二、落地：依赖契约写成可校验配置（复制即用）

架构规则若不可校验就会腐烂。在 CI 中跑依赖契约，违反即失败。

**Python — `src/backend/pyproject.toml` 追加：**

```toml
[tool.importlinter]
root_package = "app"

[[tool.importlinter.contracts]]
name = "5 层洋葱单向依赖 (AR-01)"
type = "layers"
layers = [
    "app.api",              # L4
    "app.application",      # L3
    "app.domain",           # L2
    "app.infrastructure",   # L1（由依赖倒置，被 L2 接口约束）
]

[[tool.importlinter.contracts]]
name = "领域层不依赖框架/ORM (AR-01)"
type = "forbidden"
source_modules = ["app.domain"]
forbidden_modules = ["fastapi", "sqlalchemy", "httpx", "redis", "anthropic", "openai"]

[[tool.importlinter.contracts]]
name = "新 Adapter 不准改 domain (AR-02)"
type = "forbidden"
source_modules = ["app.infrastructure.adapters"]
forbidden_modules = ["app.domain.*"]  # 只能 import domain 中的接口，不能动实现
```

**TypeScript — `src/frontend/.dependency-cruiser.cjs`**：配 `no-circular` 与 UI/store/api 层间禁向规则，挂入 pre-commit。

跑：
```bash
cd backend && lint-imports
cd frontend && npx depcruise --config .dependency-cruiser.cjs src
```

红线 AR-01/AR-02 全部由工具拦截。AR-03/AR-04/AR-05/AR-06 工具难抓，列入 §六检查清单与 PR Review。

---

## 三、5 层洋葱「代码放哪层」决策表

```
L5 表现层 (Presentation)  →  L4 接口层 (API)  →  L3 应用层 (Application)
                                                       ↓
                                              L2 领域层 (Domain)
                                                       ↑
                                       L1 基础设施层 (Infrastructure)
                                       ↑ 实现 L2 定义的接口（依赖倒置）

依赖方向：L5 → L4 → L3 → L2 ← L1
```

| 这段代码是…… | 放哪层 | 对应目录 | 不应包含 |
|--------------|--------|----------|----------|
| React 组件、页面、UI 状态 | L5 | `src/frontend/src/` | 业务规则 |
| HTTP 路由、WS endpoint、Pydantic 入参 | L4 | `src/backend/app/api/` | 业务逻辑、DB 访问 |
| Service 用例编排、事务边界、Command/DTO | L3 | `src/backend/app/application/` | 实体规则、外部调用细节 |
| 实体（Agent/Task/Group/Message）、Task Engine、领域服务、Repository 接口 | L2 | `src/backend/app/domain/` | DB / Redis / HTTP 框架（禁 import） |
| LLM Adapter、Repository 实现、Redis、WS 实现、Coordinator | L1 | `src/backend/app/infrastructure/` | 业务判断 |
| Pydantic v2 IO 模型 | 跨层（DTO） | `src/backend/app/schemas/` | 业务规则 |
| DI 容器、配置加载、CORS / 日志中间件 | 横切 | `src/backend/app/core/` | 业务规则 |

---

## 四、AgentHub 架构关键决策

### 4.1 LLM 接入：SDK/CLI 双轨（CLI 优先）

ADR `worklogs/decisions/0001-cli-first-pivot.md` 决议：CLI 模式（`ClaudeCodeRuntime` 等）是默认路径，SDK 仅作降级。原因：CLI 提供更稳定的输出格式 + 项目级 Skill 体系 + 多模型代理（见 `docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md`）。

| 维度 | SDK 模式 | CLI 模式（默认） |
|------|---------|-----------------|
| 实现位置 | `src/backend/app/infrastructure/llm/sdk/` | `src/backend/app/infrastructure/llm/cli/` |
| 适配契约 | `LLMAdapter` | `LLMAdapter` + `AgentRuntime` |
| 选型范围 | OpenAI / Anthropic SDK | Claude Code / Codex / TRAE CLI |

### 4.2 新 Agent 系统接入（落实 AR-02）

新增 Agent 系统（如 Claude/Codex/TRAE）的标准流程：

1. 在 `src/backend/app/infrastructure/adapters/` 创建 `xxx_adapter.py`
2. 继承 `base.LLMAdapter`，实现 `chat()` / `stream_chat()` / `get_capabilities()`
3. 内部通过 `provider + model + api_key + base_url` 配置底层 LLM
4. **禁止**修改 `src/backend/app/domain/` 中任何代码以适配新系统

适配器接口契约见 [docs/specs/04c-adapter-interface_适配器接口规范.md](../specs/04c-adapter-interface_适配器接口规范.md)。

### 4.3 Task Engine 与 Harness（落实 AR-03 / AR-05）

- **Harness** = `src/backend/app/domain/task_engine.py`：纯 Python 确定性逻辑（FSM 转换、Guard、幂等校验、环检测、预算校验）
- **Coordinator Agent**（LLM 驱动）：输出结构化 JSON 决策（如"分派子任务"），Harness 接收后**有权否决**（环、预算、负载超限）
- **状态变更必须**：`guard_check()` → `fsm.transition()` → 写入 `tasks.status` + 事件流（带幂等键）
- 禁直接 `task.status = "completed"` 风格的字段赋值

### 4.4 Agent 间通信（落实 AR-04）

```
❌ AgentA.send_to(AgentB, payload)       # 不允许

✅ AgentA.write(Blackboard.artifact)     # 共享制品
   Coordinator.review() → broadcast()     # 提案审查广播

✅ AgentA.propose(change)                 # 通过 Coordinator
   Coordinator.evaluate() → AgentB.consume()
```

### 4.5 配置管理（红线级）

| 规则 | 要点 |
|------|------|
| 密钥环境变量注入 | 不入代码 / 配置文件（详见 [02 CR-10](02-coding_代码编写规范.md)） |
| `.env.example` 模板 | 真实 `.env` 不入库；新人按 example 填充 |
| 分环境 | `dev` / `test` / `staging` / `prod` 各自独立 |
| Agent system ≠ model | `agent_system` 与 `provider+model+api_key+base_url` 独立配置（AR-06） |

### 4.6 技术选型（结论写入 ADR）

成熟稳定 > 新奇；社区活跃 > 功能强大；团队熟悉 > 理论最优；够用 > 过度准备。
选型理由写入 ADR（`worklogs/decisions/NNNN-<slug>.md`，仅[收束节点](ai-workflow_AI协作开发流程/06-第三步_收束节点.md)产出）。

---

## 五、反模式

### ❌ Domain 层 import 框架

```python
# src/backend/app/domain/agent.py
from fastapi import HTTPException        # ← 违反 AR-01
from sqlalchemy import Column            # ← 违反 AR-01
```
✅ Domain 只 import 标准库 + 自身定义的接口。框架/ORM 在 L1 实现层使用，通过依赖注入提供给 L2 / L3。

### ❌ 跨层调用

```python
# src/backend/app/api/chat.py（L4 表现层）
@router.post("/chat")
async def send(msg: ChatIn, db: Session = Depends(get_db)):
    db.execute("INSERT INTO messages ...")   # L4 直接操作 L1
```
✅ L4 → L3 `ChatService.send()` → L2 `Message.create()` → L1 `MessageRepository.save()`。换 DB 只改 L1。

### ❌ Domain 改适配新 Agent 系统

```python
# src/backend/app/domain/agent.py
if agent.system == "claude":                 # ← 违反 AR-02
    response = claude_specific_logic(...)
elif agent.system == "codex":
    response = codex_specific_logic(...)
```
✅ `domain/agent.py` 调 `LLMAdapter` 接口；具体 system 判断与逻辑封装在 `infrastructure/adapters/{claude,codex,...}_adapter.py`。

### ❌ Harness 内调 LLM

```python
# src/backend/app/domain/task_engine.py
async def decide_next_step(task):
    return await openai.chat.completions.create(...)   # ← 违反 AR-03
```
✅ Harness 接收 Coordinator Agent 的 JSON 决策（在 L3 应用层完成 LLM 调用），Harness 仅校验并执行。

### ❌ Task 状态直接赋值

```python
# 违反 AR-05
task.status = TaskStatus.COMPLETED
db.commit()
```
✅ `fsm.transition(task, TaskEvent.FINISH, idempotency_key=...)`：内部跑 Guard，校验合法状态机转换，写入 event log。

---

## 六、检查清单（= 审查「架构层面」展开）

- [ ] **AR-01** `lint-imports` 通过：无循环依赖、5 层单向、Domain 不依赖框架/ORM
- [ ] **AR-02** 新 Agent 系统只动 `infrastructure/adapters/`，`domain/` 无新增/修改
- [ ] **AR-03** `domain/task_engine.py` 无任何 LLM / 外部 API 调用
- [ ] **AR-04** Agent 间无直接通信代码（grep `agent_a.send_to(agent_b)` 风格）
- [ ] **AR-05** 所有 `task.status` 变更走 FSM；禁字段直赋
- [ ] **AR-06** 无 `system → model` 硬编码映射；配置可独立切换
- [ ] 模块划分匹配 5 层洋葱（API/Application/Domain/Infrastructure/Core/Schemas）
- [ ] 配置走 `.env`；提供 `.env.example`；分环境
- [ ] 技术选型理由已记录（标准/团队档位：ADR）

---

## 七、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [ai-workflow 第一步·编写计划](ai-workflow_AI协作开发流程/03-第一步_编写计划.md) |
| 验收标准 | [docs/specs/01-architecture_架构定义.md](../specs/01-architecture_架构定义.md) |
| 数据流细节 | [docs/specs/01b-architecture-design_分层与数据流.md](../specs/01b-architecture-design_分层与数据流.md) |
| 适配器接口 | [docs/specs/04c-adapter-interface_适配器接口规范.md](../specs/04c-adapter-interface_适配器接口规范.md) |
| CLI 流程 | [docs/specs/04b-adapter-cli-flow_适配器CLI流程分析.md](../specs/04b-adapter-cli-flow_适配器CLI流程分析.md) |
| Agent 边界 / 权限矩阵 | [99-boundaries_边界矩阵](99-boundaries_边界矩阵.md) |
| 密钥 / 代码级安全 | [02-代码编写规范 CR-10](02-coding_代码编写规范.md) |
| 调用图 / 依赖黑洞 | [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) |
| CLI 优先 ADR | [worklogs/decisions/0001-cli-first-pivot.md](../../worklogs/decisions/0001-cli-first-pivot.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线替换为 AR-01~06；落地配置切到 AgentHub backend 5 层洋葱；新增 §4 AgentHub 架构关键决策（CLI 双轨 / Adapter / Task Engine / Agent 通信） |
