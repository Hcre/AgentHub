# 测试规范 — AgentHub

> **本规范是 [ai-workflow 第二步·迭代开发](ai-workflow_AI协作开发流程/04-第二步_迭代开发.md) 两个环节的细化**：
> - 细化 **§2.1 TDD 自检**（先写测试 → 实现 → 重构）
> - 细化 **§2.2 可观测验证** —— 测试断言 / 覆盖率全绿是合格证据
>
> AgentHub 完整测试用例清单在 [docs/specs/05-testing-strategy_测试策略.md](../specs/05-testing-strategy_测试策略.md)；本规范定义**测试编写规则**。
> 覆盖率目标：**后端 ≥ 80%（行）+ 70%（分支），前端 ≥ 70%**。
>
> **v3.1 增补**：新增 §二点五「BDD+TDD 双循环流程」—— 业务需求侧用 BDD（Given/When/Then）冻结契约 + 实现侧用 TDD（红→绿→重构）落地测试。BDD 场景权威源 [04-commands_命令接口.md §六](../specs/04-commands_命令接口.md)。

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

**`src/backend/pyproject.toml`：**

```toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-fail-under=80 --cov-branch --cov-report=term-missing"
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
omit = ["app/alembic/*", "tests/*"]
```

**`src/frontend/package.json`（vitest）**：

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

## 二点五、BDD+TDD 双循环流程（v3.1 新增）

> **为什么加这一节**：TDD 只回答「代码写对了吗」，**不回答**「代码做的是对的事吗」。BDD 用业务语言（Given/When/Then）冻结需求契约，**TDD 写 BDD 的实现测试**。两者串成「业务需求 → 契约 → 测试 → 实现 → 验证」闭环。
>
> **场景规模**：roadmap §8 P0-1~6 / P1-1~4 / P2 缺口 = **~25 个 P 任务**。每个 P 任务对应 04-commands §六 1 个或多个 BDD 场景，**约 35-50 个 BDD 场景**需落地。

### 2.5.1 BDD 场景权威源

**文件**：`docs/specs/04-commands_命令接口.md` §六

**场景 ID 格式**：`B-<PRD章节>-<P级别>-<序号>`
- `<PRD章节>` ∈ {1 IM聊天, 2 Orchestrator, 3 多Agent接入, 4 产物预览, 5 部署, 6 多端, 7 降级}
- `<P级别>` ∈ {P0, P1, P2, P3}
- `<序号>` = 2 位数字（`01`, `02`, ...）

**当前 16+ BDD 场景**（per 04-commands §六 v2.2，2026-06-07 落档）：
- IM 聊天：S01 搜索 / S02 置顶 / S03 回复 / S04 引用 / S05 重新生成 / P0-04 Pin 所有权
- Orchestrator：P2-F01 失败降级
- 多 Agent 接入：A01 对话式自建 / A02 表单式自建
- 产物预览：D01 文档渲染 / D02 全屏预览 / D03 Monaco 编辑器
- 部署：P2-DP01 部署卡
- 多端：P2-M01 移动端 H5 / P2-V01 v6 录制
- 监控：P1-2 Token 消耗 / P1-3 CLI PATH 扫描
- 降级：P2-FD01 降级矩阵

**BDD ↔ 任务映射表**：见 [04-commands §七 BDD↔任务映射速查表](../specs/04-commands_命令接口.md#七bdd-任务映射速查表)

### 2.5.2 BDD 三件套（Given/When/Then）

每个 BDD 场景必须有 3 部分（**缺一不可**）：

```markdown
| 项 | 内容 |
|----|------|
| **场景 ID** | `B-1-P0-04` Pin 消息 session 所有权校验 |
| **对应任务** | roadmap §8.1 P0-4 |
| **API 端点** | `POST /api/messages/{id}/pin?session_id=<sid>` |
| **Given** | (a) S1 私聊 U1 + U2 两人均参与；(b) S1 中 M1（U1 发） + M2（U2 发）；(c) U1 持有效 JWT |
| **When-1（合法）** | `POST /api/messages/M1/pin?session_id=S1` |
| **Then-1** | (a) HTTP 204；(b) DB `pinned_by_user_id=U1.id, pinned_at=now()` |
| **When-2（非法 — 跨用户）** | `POST /api/messages/M2/pin?session_id=S1`（U1 想 pin U2 的消息）|
| **Then-2** | **HTTP 403** `{error:{code:"E_MESSAGE_PIN_NOT_OWNER",message:"..."}}` |
| **When-3（非法 — session 不一致）** | `POST /api/messages/M1/pin?session_id=S99` |
| **Then-3** | HTTP 422 `{error:{code:"E_MESSAGE_PIN_SESSION_MISMATCH",message:"..."}}` |
| **边界 N** | ...（必加 401 / 403 / 404 / 422 错误码覆盖）|
| **UI 验收（Playwright E2E）** | M1 hover → Pin 按钮 → click → M1 顶部图钉 icon |
```

**写 BDD 必走 5 步**：

1. **Given 段**：列数据 + 鉴权 + 状态（每条带 (a)/(b)/(c) 编号）
2. **When 段**：分多个 When-1/When-2/When-3，**至少 1 个合法 + 1 个非法 + 1 个边界**
3. **Then 段**：每个 When 对应 1 个 Then，**断言 3 件事**（HTTP 状态 / 响应体 / DB 副作用 / WS 推送 至少 2 件）
4. **错误码**：必加「错误 401 / 403 / 422 / 404」覆盖
5. **UI 验收**：必加「UI 验收（Playwright E2E）」段，描述关键 DOM 断言

### 2.5.3 BDD → TDD 翻译（AAA + 命名）

**TDD 循环**（每个 BDD When-Then 对应 1 轮）：

```
红（写测试）：把 BDD When-Then 转成 AAA 单元测试
    ↓
绿（实现）：最小代码让测试通过
    ↓
重构：清代码坏味道 + 保持测试绿
```

**翻译模板**（Python pytest）：

```python
# 来自 BDD B-1-P0-04 When-2（非法 — 跨用户）
def test_pin_message_cross_user_returns_403():
    # Arrange（对应 BDD Given）
    u1 = create_user(name="U1")
    u2 = create_user(name="U2")
    s1 = create_private_session(participants=[u1, u2])
    m1 = create_message(session=s1, sender=u1, content="...")
    m2 = create_message(session=s1, sender=u2, content="...")
    jwt_u1 = issue_jwt(u1)
    # Act（对应 BDD When-2）
    response = client.post(
        f"/api/messages/{m2.id}/pin?session_id={s1.id}",
        headers={"Authorization": f"Bearer {jwt_u1}"},
    )
    # Assert（对应 BDD Then-2）
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "E_MESSAGE_PIN_NOT_OWNER"
    # DB 副作用
    m2_reloaded = db.query(Message).get(m2.id)
    assert m2_reloaded.pinned_by_user_id is None
```

**翻译模板**（TypeScript vitest，前端组件）：

```typescript
// 来自 BDD B-1-P0-04 UI 验收
describe('MessageBubble Pin button', () => {
  it('S2 群聊消息 hover 后显示 Pin 按钮且可点击', async () => {
    // Arrange
    const m1 = { id: 'M1', content: '...', pinned_by_user_id: null, sender: { id: 'U1' } };
    const currentUser = { id: 'U1', jwt: 'xxx' };
    render(<MessageBubble message={m1} currentUser={currentUser} sessionId="S1" />);
    // Act
    fireEvent.mouseEnter(screen.getByTestId('message-bubble'));
    const pinBtn = await screen.findByRole('button', { name: /pin/i });
    fireEvent.click(pinBtn);
    // Assert
    await waitFor(() => {
      expect(pinBtn).toHaveAttribute('aria-pressed', 'true');
    });
    // fetch mock 验证
    expect(mockedFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/messages/M1/pin?session_id=S1'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
```

**命名规范**（强制）：

| 语言 | 命名 | 例子 |
|------|------|------|
| Python | `test_<方法>_<场景>_<期望>` | `test_pin_message_cross_user_returns_403` |
| TypeScript | `test_<method>_<scenario>_<expected>` 或 vitest `it('<scenario> <expected>')` | `test('Pin button on hover', async () => {...})` |

### 2.5.4 BDD+TDD 双循环工作流（每 P 任务必走）

```
第 1 阶段  计划
  ├─ 读 roadmap §8 P 任务表 + STATUS.md
  ├─ 找 04-commands §六 对应 BDD 场景
  └─ 写 BDD（如缺失）— Spec 同步先于实现（PR-09）

第 2 阶段  落地
  ├─ 拉分支 feature/<domain>/<desc>（PR-02）
  ├─ 转 BDD Given/When/Then → AAA 测试
  │   ├─ 后端：1 个 When → 1 个 pytest 单元测试 + 1 个 httpx 集成测试
  │   ├─ 前端：1 个 UI 验收 → 1 个 vitest 组件测试
  │   └─ E2E：1 个 P 任务 → 1 个 Playwright 脚本（6+ 章节）
  ├─ 跑测试 → 全部红
  ├─ 实现最小代码
  ├─ 跑测试 → 全部绿
  └─ 重构 + 保持绿

第 3 阶段  验证
  ├─ 跑覆盖率（≥ 80% 后端 / ≥ 70% 前端）
  ├─ 跑 CR 自查（AR/CR/PR/AP/T/D 红线）
  ├─ 跑 6 E2E（凌晨冲刺模式 + 截图存 docs/deliverables/）
  ├─ 写 worklog + 更新 STATUS.md
  └─ commit + push（user 偏好直推 main）
```

### 2.5.5 BDD vs TDD vs E2E 分工

| 层 | 来源 | 工具 | 数量级 | 触发时机 |
|----|------|------|--------|---------|
| **BDD** | [04-commands §六](../specs/04-commands_命令接口.md) | 文档（Given/When/Then）| ~35-50 场景 | 任务开工前冻结 |
| **TDD 单元** | BDD When-Then 转 AAA | pytest / vitest | ~150-300 用例 | 每次 commit |
| **TDD 集成** | BDD UI 验收 + API 端点契约 | pytest + httpx / vitest + msw | ~50-80 用例 | 每次 PR |
| **E2E** | 5 个 Core User Story + P 任务演示 | Playwright | ~20-30 脚本 | 每 M 结束 / 答辩前 |

### 2.5.6 BDD+TDD 反模式（违反 T-01~06）

| ❌ 反模式 | ✅ 正确做法 |
|---------|----------|
| BDD 写「用户登录」无具体端点 / 数据 | BDD 写「POST /api/auth/login with body {email, password} → 200 {token, user}」|
| BDD 漏错误码覆盖 | 必加 401/403/404/422 至少 1 个 |
| BDD 漏边界条件 | 必加「空数组 / null / 大文件 / 超时」至少 1 个 |
| TDD 写「test_dispatch」（无场景无期望）| 改 `test_dispatch_no_mentions_falls_back_to_coordinator` |
| TDD 测 happy path 不测异常 | 1 happy + 1 异常 + 1 边界 = 至少 3 用例 / 场景 |
| TDD Mock 内部 service（违反 T-02）| 只 Mock 外部边界（LLM API / GitHub / Cloudflare）|
| TDD 跨测试共享全局变量（违反 T-01）| 每个测试 Arrange 阶段自建数据，fixture scope=function |
| 写完实现才补 BDD | BDD 必须**开工前冻结**（PR-09 spec 同步先于实现）|
| BDD 与 TDD 描述不一致 | BDD 改了必须**同步改 TDD 用例名 / 断言** |

### 2.5.7 BDD+TDD 工具链（AgentHub 实测）

| 工具 | 用途 | 命令 / 配置 |
|------|------|------------|
| pytest | Python 单元 + 集成 | `cd src/backend && pytest -q --cov=app --cov-fail-under=80` |
| pytest-asyncio | async 测试 | `asyncio_mode = "auto"` in `pyproject.toml` |
| httpx | FastAPI 集成测试 | `client = TestClient(app)` + `httpx.AsyncClient` |
| vitest | 前端单元 + 组件 | `cd src/frontend && npx vitest run --coverage` |
| @testing-library/react | React 组件测试 | `render` + `screen.getByRole` + `fireEvent` |
| msw | API mock（前端）| `setupServer` + `rest.post('/api/...')` |
| Playwright | E2E | `python scripts/e2e_<feature>.py` |
| pytest-cov | 覆盖率 | `--cov-branch --cov-report=term-missing` |
| fakeredis | Redis mock | `fakeredis.aioredis.FakeRedis` |
| testcontainers | 真实 PG/Redis | `from testcontainers.postgres import PostgresContainer` |

### 2.5.8 BDD+TDD 检查清单

**BDD 写完时**：
- [ ] 场景 ID 格式 `B-<PRD>-<P级别>-<序号>`
- [ ] 3 件套（Given/When/Then）齐全
- [ ] 至少 1 合法 + 1 非法 + 1 边界 When-Then
- [ ] 错误码覆盖（401/403/404/422 至少 1）
- [ ] UI 验收段（Playwright E2E）描述关键 DOM 断言
- [ ] 在 [04-commands §七 BDD↔任务映射表](../specs/04-commands_命令接口.md#七bdd-任务映射速查表) 追加 1 行

**TDD 实现时**：
- [ ] 每个 When-Then → 1 个 AAA 测试（命名规范）
- [ ] 红 → 绿 → 重构循环走完
- [ ] 不 Mock 内部模块（T-02）
- [ ] 覆盖率 ≥ 档位目标（核心 domain 90% / service 80% / API 80% / infra 70%）
- [ ] Adapter 覆盖 5 场景（T-05：成功 / 限流 / 超时 / key 失效 / 流式中断）
- [ ] FSM 覆盖 4 场景（T-06：合法 / 非法 / 幂等 / 边界）

**E2E 验证时**：
- [ ] 6+ 章节脚本（凌晨冲刺模式）
- [ ] 截图存 `docs/deliverables/screenshots/e2e-<feature>-F1..F6-*.png`
- [ ] 写 `docs/deliverables/integration-verify-<feature>.md` 报告
- [ ] 5/6 PASS 标准（1 个 downscope 透明声明）

### 2.5.9 BDD+TDD 落地里程碑

| 里程碑 | BDD 完成 | TDD 完成 | E2E 完成 |
|--------|---------|---------|---------|
| **当前（2026-06-07）** | §六 16+ 场景冻结 | 47+11=58 单测绿（凌晨冲刺 + E2E session）| 10 screenshot + 6 E2E 集成验证 |
| **M5 收束** | §六 25+ 场景（补 P0-4 后端校验 / P1-2 / P1-3 / 4 P2 缺口）| ≥ 80 单测 | 6+ E2E 验证 P0/P1 全 PASS |
| **M6 答辩** | 35+ 场景 | ≥ 150 单测 | 8 E2E 覆盖 5 Core User Story |
| **MVP 2.0（远期）** | 50+ 场景 | ≥ 300 单测 | 12+ E2E + CI gate 全绿 |

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
| 完整测试用例清单 | [docs/specs/05-testing-strategy_测试策略.md](../specs/05-testing-strategy_测试策略.md) |
| 数据模型（用于构造测试 fixture） | [docs/specs/03-data-model_数据模型.md](../specs/03-data-model_数据模型.md) |
| 影响分析 / 调用图驱动增量测试 | [08-代码理解与图谱规范](08-code-understanding_代码理解与图谱规范.md) |
| 错误处理（测异常路径） | [02-代码编写规范 §四](02-coding_代码编写规范.md) |

---

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2026-05-28 | v3.0 | 按模板骨架重写；红线新增 T-05/T-06（Adapter + FSM 必测场景）；Mock 边界改为 AgentHub 实测（Testcontainers 跑真实 PG/Redis）；覆盖率目标按层细化；接入 E2E Core User Stories |
| 2026-06-07 | v3.1 | 新增 §二点五「BDD+TDD 双循环流程」—— 16+ BDD 场景（04-commands §六）+ AAA 翻译模板 + 红→绿→重构循环 + 工具链 + 反模式 + 落地里程碑（M5/M6/MVP 2.0 三档 BDD/TDD/E2E 数量目标）|
