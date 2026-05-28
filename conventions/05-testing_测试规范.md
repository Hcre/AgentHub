# 测试规范 — AgentHub

> **本规范是 [ai-workflow 第二步·迭代开发](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) 两个环节的细化**：
> - 细化 **§2.1 TDD 自检**（先写测试 → 实现 → 重构）
> - 细化 **§2.2 可观测验证** —— 测试断言 / 覆盖率全绿是合格证据
>
> AgentHub 完整测试用例清单在 [docs/specs/05-testing-strategy_测试策略.md](../docs/specs/05-testing-strategy_测试策略.md)；本规范定义**测试编写规则**。
> 覆盖率目标：**后端 ≥ 80%（行）+ 70%（分支），前端 ≥ 70%**。

---

## 一、红线（必守）

| # | 红线 | 怎么自动抓 |
|---|------|-----------|
| **T-01** | 测试独立：不依赖执行顺序、不共享全局状态 | `pytest -p no:randomly` 乱序跑仍全绿 |
| **T-02** | 只 Mock 外部边界（LLM API / GitHub Actions / Cloudflare）；**真实 PG + Redis + WS**（Testcontainers） | CR + Mock 边界对照表（§三） |
| **T-03** | 覆盖正常 + 边界 + 异常路径；不只测 happy path | CR + 分支覆盖率 |
| **T-04** | 无 flaky test；出现立即修，禁「重跑就行」 | CI 重试检测 |
| **T-05** | Adapter 测试必须覆盖：成功 / 限流 / 超时 / API key 失效 / 流式中断 | CR |
| **T-06** | FSM 状态转换测试覆盖：合法转换 / 非法拒绝 / 幂等键去重 / 边界条件 | CR |

---

## 二、落地：TDD 节奏 + 覆盖率门禁

**TDD 循环**：红（写失败测试）→ 绿（最小实现）→ 重构。每个功能点的 BDD 场景逐条转成测试用例。

**AAA 模板 + 命名 `test_<方法>_<场景>_<期望>`：**

```python
def test_dispatch_router_resolve_auto_with_mentions_returns_mentioned_agent():
    # Arrange
    msg = ChatMessage(content="@FrontendAgent 帮我看看这个", mentions=["FrontendAgent"])
    router = DispatchRouter()
    # Act
    result = router.resolve(msg, mode="auto")
    # Assert
    assert result.target_type == "agent"
    assert result.target_id == "FrontendAgent"
```

**`backend/pyproject.toml`：**

```toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-fail-under=80 --cov-branch --cov-report=term-missing"
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
omit = ["app/alembic/*", "tests/*"]
```

**`frontend/package.json`（vitest）**：

```json
{
  "scripts": {
    "test": "vitest run --coverage",
    "test:watch": "vitest"
  }
}
```

**CI（每次 PR）**：
```bash
# 后端
cd backend && pytest -q          # < 30s 必过；< 80% 阻止合入
# 前端
cd frontend && npm test          # < 70% 提示
```

---

## 三、决策表 / 速查

### AgentHub 测试金字塔

```
         ┌──────┐
         │ E2E  │  ~20 场景    Playwright           每 M 结束
         ├──────┤
         │ 集成  │  ~50 用例    pytest + testcontainers  每 PR
         ├──────┤
         │ 单元  │  ~150 用例   pytest + vitest          每 commit
         └──────┘
```

### Mock 边界（AgentHub 实测约定）

| 该 Mock | 不该 Mock（真实服务） |
|---------|---------------------|
| LLM API（Claude / DeepSeek / Codex / TRAE）→ JSON fixture（正常 / 异常 / 流式 / 超时） | PostgreSQL → Testcontainers |
| Claude Code / Codex CLI subprocess → 预录输出 | Redis → Testcontainers |
| GitHub Actions webhook | WebSocket → 真实连接 |
| Cloudflare Tunnel | Alembic migration → 真实 apply |
| `datetime.now()` / 随机数 / `uuid.uuid4()` | 项目内部模块（service / domain） |

### 什么该测

| 优先测 | 不必测 |
|--------|--------|
| 核心业务（task_engine、coordinator、dispatch_router、mention_router） | 第三方库内部 |
| Adapter（每种 LLM 系统的成功/限流/超时/key失效） | 简单 getter/setter |
| FSM 转换（合法/非法/幂等键去重） | 纯配置 |
| 安全（加密 encrypt/decrypt、JWT 校验、密钥脱敏） | 自动生成代码 |
| 边界值（空成员群组 / 嵌套层级 > 1 / 极大 token） | 框架能力（FastAPI 路由本身） |

### 覆盖率目标

| 模块类型 | 行覆盖 | 分支覆盖 |
|----------|--------|----------|
| 核心 domain（task_engine、coordinator、FSM） | ≥ 90% | ≥ 85% |
| Service / Application（L3） | ≥ 80% | ≥ 70% |
| API 层（L4） | ≥ 80% | ≥ 70% |
| Infrastructure / Adapter（L1） | ≥ 70% | ≥ 60% |
| 前端组件 | ≥ 70% | ≥ 60% |
| 前端 store / hook | ≥ 80% | ≥ 70% |

### 集成测试关键场景（部分）

| 端点 / 模块 | 必测场景 |
|------------|---------|
| `POST /api/agents` | Claude/Codex/Trae 三种系统 / name 重复 / api_key 加密落库 |
| `POST /api/sessions/{id}/messages` | auto→协调者 / auto→Agent / auto→意图检测 / direct |
| `POST /api/tasks` | 手动创建 / assignee 校验 / 嵌套 > 1 拒绝 |
| WebSocket | 连接认证 / 流式推送 / 心跳 / 断线重连增量 |
| Migration | 全部正向 apply + 全部反向 rollback |
| 事件溯源 | 正常重建 / 空事件 / 幂等键去重 |
| 并发任务领取 | `SKIP LOCKED` 两个 Worker 不同时领同一任务 |

### E2E 必走的 Core User Stories（5 条）

| # | Story | M |
|---|-------|----|
| E2E-01 | 创建 Agent → 私聊 → 流式回复 → 代码块渲染 | M2 |
| E2E-02 | 创建群组 → 多 Agent → 协调者分解 → 并行 → 结果合并 | M3 |
| E2E-03 | Agent 返回代码 → Diff 卡片绿红标注 → iframe 预览 → 确认 | M4 |
| E2E-04 | Harness 注入 GlobalContext → Worker 引用共享制品 | M3 |
| E2E-05 | 创建 Agent 向导 → 配 DeepSeek → Agent 可调度 | M4 |

---

## 四、反模式

### ❌ 依赖执行顺序

```python
# test_create.py
def test_create_agent():
    global created_agent_id
    created_agent_id = agent_service.create(...).id

# test_update.py（必须在 test_create 之后跑才行）
def test_update_agent():
    agent_service.update(created_agent_id, ...)   # ← 单跑必崩
```
✅ 每个测试 Arrange 阶段自建数据；fixture 用 `pytest.fixture(scope="function")`。

### ❌ Mock 了不该 Mock 的（违反 T-02）

```python
# 错：Mock 了内部的 DispatchRouter
def test_chat_message_handler():
    router = Mock(spec=DispatchRouter)
    router.resolve.return_value = ResolveResult(target_type="agent", ...)
    handler.process(msg, router=router)
    # ← 测的是 Mock，DispatchRouter 真实逻辑从未执行
```
✅ DispatchRouter 走真实代码；只 Mock LLM API 与外部网络。

### ❌ 只测 happy path

```python
# 错：只测正常分发
def test_dispatch_normal():
    assert router.resolve(normal_msg).target_id == "AgentA"
```
✅ 补：`test_dispatch_no_mentions_falls_back_to_coordinator`、`test_dispatch_invalid_agent_id_raises`、`test_dispatch_token_budget_exceeded_rejects`、`test_dispatch_circular_dependency_detected` ……

### ❌ Adapter 只测成功路径（违反 T-05）

只有 `test_claude_adapter_success` → 限流、超时、key 失效、流式中断都漏了。
✅ 每个 Adapter 至少 6 用例：成功 / 429 限流 / 超时 / 401 key 失效 / 503 上游不可用 / 流式中断恢复。

### ❌ flaky test 用 `@pytest.mark.flaky(reruns=3)` 掩盖

时过时不过 → 标记重试 → 问题被埋掉，几月后炸在 prod。
✅ 立即定位（多半是时间/竞态/全局状态），修了再合并。CI 检测到 retry 即报警。

---

## 五、检查清单

- [ ] **T-01** 测试独立；`pytest -p no:randomly` 乱序跑仍全绿
- [ ] **T-02** 只 Mock 外部边界（LLM / GitHub / Cloudflare），不 Mock 内部模块
- [ ] **T-03** 覆盖正常 + 边界 + 异常，不只 happy path
- [ ] **T-04** 无 flaky test 标记
- [ ] **T-05** Adapter 覆盖 成功/限流/超时/key失效/流式中断（每种）
- [ ] **T-06** FSM 覆盖 合法/非法/幂等/边界
- [ ] 命名 `test_<方法>_<场景>_<期望>`，遵循 AAA
- [ ] 集成测试用 Testcontainers（真实 PG + Redis）
- [ ] 覆盖率达档位目标，CI 全绿
- [ ] 影响分析：本 PR 改动的模块对应的测试已跑（中大型项目用调用图增量定位，见 [08](08-code-understanding_代码理解与图谱规范.md)）

---

## 六、关联

| 方向 | 链接 |
|------|------|
| 细化自 | [ai-workflow §2.1 TDD / §2.2 可观测验证](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) |
| 完整测试用例清单 | [docs/specs/05-testing-strategy_测试策略.md](../docs/specs/05-testing-strategy_测试策略.md) |
| 数据模型（用于构造测试 fixture） | [docs/specs/03-data-model_数据模型.md](../docs/specs/03-data-model_数据模型.md) |
| 影响分析 / 调用图驱动增量测试 | [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) |
| 错误处理（测异常路径） | [02-代码编写规范 §四](02-coding_代码编写规范.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线新增 T-05/T-06（Adapter + FSM 必测场景）；Mock 边界改为 AgentHub 实测（Testcontainers 跑真实 PG/Redis）；覆盖率目标按层细化；接入 E2E Core User Stories |
