# Phase 5 规格 — 接线（task_engine → AgentHub 系统）

> 日期：2026-06-06（v2 重写）| 属于：[[coordinator-mvp-implementation-plan]] Phase 5
> 前提：5 协作者真实现全部落地（planner/verifier/executor/orchestrator/scheduler，已测）。
> 本相回归面最大，是 task_engine 子系统接入消息循环的最后一相。
>
> **v2 重写说明**：v1 spec 建立在"ChatService 调 Selector.pick"这一**错误前提**上——实测
> `Selector.pick` 只在 `discussion_orchestrator.py:109` 被调用，ChatService 不持有 Selector。
> v2 把模式闸门下沉到真实前门 `ChatService._handle_group`，**Selector 一行不改**（回归面归零），
> 并修正 v1 的 5 处与真实代码不符之处（详见 §11 勘误）。

---

## 0. 核心定位与设计原则

把 task_engine 接进 AgentHub 消息循环：用户发任务 → ChatService 前门判 decompose → 起后台
Orchestrator → 群成员 Agent（worker）执行 → 完成后系统消息汇总。

**三条设计原则（决定全篇取舍）**：

1. **Selector 零改动**。design §13.3 硬约束"Selector 是无状态廉价路由器"。decompose 是
   **会话模式决策**（owns 生命周期、能 spawn 后台任务、持 registry），不是**发言选择**
   （谁说话）。两者不同层 → 模式闸门放 ChatService（真实前门），发言选择留 Selector
   （在 DiscussionOrchestrator 内）。Selector 永远在"无 coordinator"语境被调，故**不需要**
   `active_coordinator` 参数。
2. **后台任务隔离**。Coordinator 跑几分钟，绝不塞进 `send_and_stream` 的同步子流。
   `asyncio.create_task` fire-and-forget，进度经系统消息异步落库广播。
3. **MVP 减法优先**。串行（concurrency=1）、单 active run/session、执行态仅 control（停/取消），
   非 control 消息忽略。busy 路由 / 执行态改需求 = 标准档（§11.9/A2），**本相不做**。

**5 根接线**（v1 的 #5 busy 路由移出 MVP，见 §11 勘误 E4）：

| # | 接线 | 改什么 |
|---|------|--------|
| 1 | 模式闸门（decompose 识别 + control 识别） | 新建 `coordinator_gate.py` |
| 2 | ChatService 前门分支 → 起后台 Orchestrator | `chat_service.py` |
| 3 | TextLLM 适配器接 Anthropic（Planner 用） | 新建 `text_llm_adapter.py` |
| 4 | CoordinatorRun 后台任务 + registry（防重/取消） | 新建 `coordinator_run.py` |
| 5 | DI 注入（gate 进 ChatService） | `api/deps.py` ×2 + `api/ws/chat.py` ×1 |

---

## 1. 需求 / 约束 / 边界 / 验收

### 1.1 需求（做什么）

| 组件 | 职责 |
|------|------|
| **CoordinatorGate** | 纯决策。`has_work_intent`（机械预滤，零 LLM）+ `is_decompose`（1 次 LLM 二分类，超时降级 discuss）+ `is_control`（停/取消，零 LLM）。不碰 Selector |
| **ChatService 前门** | `_handle_group` 在 @mention 分支后、mode 分派前插入闸门：执行态→control/忽略；讨论态→命中则 `_start_coordinator`，否则原 mode 分派（一行不改） |
| **CoordinatorRun** | 包 `Orchestrator.run()` 为后台 task。完成→final_answer 系统消息；异常→错误系统消息；终→registry 释放。持 session 级 registry（防重） |
| **AnthropicTextLLM** | 实现 `TextLLM` Protocol：`complete(prompt)→str`。只做调用，容错归 Planner |
| **resolve_agent** | spawn 时 async 预解析 `member_ids → {name: Agent}`，闭包成**同步** `resolve` 喂 Executor |

### 1.2 约束

- **Selector `pick` 不动**：A1 逻辑在 ChatService 前门，独立于发言选择。纯讨论零 LLM 回归。
- **`send_and_stream` 不改成后台循环**：decompose 分支起后台 task 后**立即结束本请求**（不 yield worker 流）。
- **TextLLM 只调用不容错**：Planner 已有 `extract_json` + 解析重试 + API 退避（planner.py:213/233），适配器不得吞错。
- **worker = 群成员 Agent**：Executor 复用 `build_adapter_for_agent` + `adapter.stream`（Phase 4 已定）。
- **workspace 来源**：`Session.workspace_path`（session.py:24，已有字段；空串 → 视为无仓库）。

### 1.3 边界（不做什么）

- 不做 ContextHandoff 交接压缩 — MVP `task=trigger.content`，`constraints=()`。
- 不做 WS 任务面板 — `event_sink=None`（Executor 默认 no-op，executor.py:81/124）。
- 不做 A2 全量（question/modification 分类）— 执行态非 control 消息忽略。
- 不做 **busy 路由**（@忙碌 worker 拦截）— 标准档（理由见 §11 勘误 E4）。
- 不做 TaskEventModel 持久化 — `Orchestrator.events` 是内存列表（orchestrator.py:49），够 MVP。
- 不做并发 / worktree — 串行。
- **decompose 仅覆盖无 @mention 的群消息**（@ 消息在 `_handle_group:146` 已被直接 streaming 截走，MVP 接受）。

### 1.4 验收（Phase 5 算完成）

- `tests/test_selector.py` 回归全绿（**零改动**，证明 Selector 未被污染）。
- `tests/test_coordinator_gate.py`（新）：预滤命中/未命中、decompose/discuss 分类、control 识别、LLM 超时降级。
- `tests/test_chat_service.py`：回归全绿 + decompose 分支 + 执行态 cancel + 防重二次 decompose。
- `tests/test_wiring.py`（新）：mock TextLLM + fake Executor/Verifier 全链路 → COMPLETED + 系统消息落库。
- ruff 干净。手动冒烟：真 CLI worker 跑最小任务（"创建 README"）。

---

## 2. 条件 → 动作（消息流）

```
用户群消息 → ChatService.send_and_stream → _handle_group
  │
  ├─ [不改] 有 @mention → _resolve_mentions → 逐个 _stream_one_agent → return
  │
  ├─ [新增] 无 @mention：模式闸门
  │     run_id = registry.get(session.id)
  │     │
  │     ├─ run_id 非空（EXECUTION 态）:
  │     │   ├─ gate.is_control(text) → _cancel_coordinator → 系统消息「已取消」→ return
  │     │   └─ 其他 → 忽略（MVP 不打断）→ return
  │     │
  │     └─ run_id 为空（DISCUSSION 态）:
  │         ├─ gate.has_work_intent(text) 且 await gate.is_decompose(text, history):
  │         │     → _start_coordinator(session, group, trigger) → return
  │         └─ 否则 → 原 mode 分派（run_discussion / 静默，一行不改）
  │
  └─ _start_coordinator: registry.try_reserve → 预解析 workers → gather_context
        → 组装 5 协作者 → CoordinatorRun.start()（后台 task）→ 本请求结束
```

| 条件 | 动作 |
|------|------|
| 讨论态 + 含工作动词 | 机械预滤命中 → 1 次 LLM 判 decompose/discuss |
| LLM 判 decompose | `_start_coordinator` 起后台 task |
| 后台 task 运行中 | Orchestrator 串行调度，状态记内存 events |
| 全部 COMPLETED | final_answer → 系统消息（role=SYSTEM）落库广播 → registry 释放 |
| Planner/Orchestrator 异常 | 错误系统消息 → registry 释放（不崩 ChatService） |
| 执行态 + "停"/"取消" | control 机械识别 → `run.cancel()` → 系统消息 → 回讨论态 |
| 执行态 + 其他消息 | MVP 忽略（标准档走 A2） |
| 执行态 + 二次工作指令 | registry 已占 → 系统消息「已有任务执行中」 |

---

## 3. 异常处理

| 异常 | 处理 |
|------|------|
| `gather_context` OSError（workspace 不可读） | context.py 已守卫：非目录 → `repo_tree=""`，不抛。Planner 基于需求文本分解 |
| `SeedPlanner.plan` 抛 `PlanEmptyError`/`PlanParseError`/`PlannerLLMError` | CoordinatorRun 捕获 → 系统消息「任务分解失败: {reason}」→ registry 释放 |
| `build_graph` 校验失败（环/悬空/未知 worker） | 在 `plan()` 内抛 → 同上路径 |
| Orchestrator 内部异常（非 worker 失败） | CoordinatorRun 捕获 → 错误系统消息 → 释放 |
| Worker 执行失败/超时 | Executor 收敛为 `WorkerOutcome(ok=False)`（executor.py:109，永不抛）→ Orchestrator retry/FAILED，属正常流 |
| 后台 task 被 cancel | `asyncio.CancelledError` 捕获 → 清理 → 释放 |
| 空 workers（群无成员） | `gather_context` workers 空 → `plan()` 抛 `PlanEmptyError`（planner.py:188）→ 系统消息「群组无可用 Agent」 |

**统一铁律**：CoordinatorRun 任何异常都不上抛。`_start_coordinator` fire-and-forget，
异常 → 日志 + 系统消息 + registry 释放，绝不让 `send_and_stream` 崩。

---

## 4. 禁止项（不允许发生）

| 禁止 | 防线 |
|------|------|
| 改动 Selector 现有 L1/L1.5/L2/L3 行为 | 闸门在 ChatService，**不 import/调用 Selector**；selector.py 零改动 |
| 纯讨论消息触发 LLM（回归） | `has_work_intent` 机械预滤先筛；无工作动词 → 直接走原逻辑，零 LLM |
| `send_and_stream` 被 Coordinator 阻塞 | CoordinatorRun 是 `create_task` 后台任务，`_start_coordinator` 不 await 其完成 |
| 同一 session 两个 active run | `registry.try_reserve` 同步 check+insert，**在任何 await 之前**（§9 竞态） |
| CoordinatorRun 异常崩 ChatService 请求 | 全异常在后台 task 内捕获，不上抛 |
| TextLLM 适配器吞错 | 只 `messages.create` + 返回 text；瞬时错误交 Planner `_complete_with_backoff` 处理 |
| 残留 old `coordinator.py`/`harness.py` stub 引用 | Phase 2/3 已删，确认无 import（grep 校验） |

---

## 5. 通过 / 不通过判定

### 5.1 算成功
- 讨论态发工作指令 → 闸门返回 decompose → 后台 task 启动。
- 全 fake 链路（mock TextLLM + fake Executor/Verifier）跑通到 COMPLETED + 系统消息落库。
- 执行态 "停" → cancel → registry 释放。
- 二次 decompose → 被 registry 拦截。

### 5.2 不算成功
- `test_selector.py` 任一回归失败（= 污染了 Selector）。
- 纯讨论触发额外 LLM（预滤未拦截）。
- CoordinatorRun 异常导致请求崩。
- 同 session 出现两个 active run。

---

## 6. 代码规范 / 错误处理 / 可测可扩展可观测

### 6.1 规范
- async + 类型注解 + ruff；禁裸 print（logging）。
- `coordinator_gate.py` ~50 行；`coordinator_run.py` ~90 行；`text_llm_adapter.py` ~30 行；
  `chat_service.py` 增量 ~70 行（闸门分支 + `_start_coordinator` + `_cancel_coordinator`）。
- 闸门逻辑全在 `coordinator_gate.py`，ChatService 只调用，不内联判断。

### 6.2 错误处理统一
- CoordinatorRun 异常 → 系统消息 + registry 释放，不上抛。
- `gate.is_decompose` LLM 超时/异常 → 返回 False（降级 discuss，宁可漏分解不误触发）。
- 后台 task cancel → 捕获 CancelledError → 清理 → 释放。

### 6.3 可测 / 可扩展 / 可观测

| 维度 | 要求 |
|------|------|
| **可测** | gate 用 mock LLM client；CoordinatorRun 用 fake 协作者（`tests/fakes.py` 已有 FakePlanner/Executor/Verifier）；ChatService decompose 分支用集成测试 + mock gate |
| **可扩展** | MVP `_active_runs` 内存 dict ↔ 标准档 Redis/DB；`event_sink=None` ↔ 标准档 WS 推送；gate 二分类 ↔ 标准档 A2 三分类 |
| **可观测** | logging 记录：decompose 触发（LLM 判词）、CoordinatorRun 启动/完成/失败、worker 名→Agent 解析。`Orchestrator.events` 内存列表已记 transition |

---

## 7. 数据结构 / 接口 I/O（全部对照真实代码）

### 7.1 CoordinatorGate（新建 `coordinator_gate.py`）

```python
_WORK_VERBS = re.compile(
    r"(帮我|帮我们|替我|给我做|实现|开发|搭建|创建|新建|修复|重构|优化|部署|发布|"
    r"加一个|新增|添加|删除|移除|拆分|合并|升级|迁移|集成|做一个|做个)"
)  # 注：去掉单字"写/改"（误命中率高，见 §11 勘误 E5）

class CoordinatorGate:
    """模式决策。不持状态，不碰 Selector。复用 Selector 同款廉价模型配置。"""
    def __init__(self, client, model: str) -> None:
        self._client, self._model = client, model

    def has_work_intent(self, text: str) -> bool:
        if not _WORK_VERBS.search(text):
            return False
        t = text.strip()
        if t.endswith(("?", "？")) and re.search(r"(怎么|如何|为什么|是什么|有没有|能不能|可不可以)", t):
            return False  # 纯提问排除
        return True

    async def is_decompose(self, text: str, history: list[Message]) -> bool:
        """1 次 LLM 二分类。异常/超时 → False（降级 discuss）。"""
        ...  # tool_use 或 structured，返回 "decompose" | "discuss"

    @staticmethod
    def is_control(text: str) -> bool:
        return bool(re.search(r"^(停|停止|取消|停下|cancel|stop|abort)", text.strip(), re.I))
```

### 7.2 AnthropicTextLLM（新建 `text_llm_adapter.py`，实现 ports.TextLLM）

```python
class AnthropicTextLLM:
    """ports.TextLLM 的 Anthropic 实现。只做调用，容错归 Planner（ports.py:57）。"""
    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        self._client, self._model = client, model

    async def complete(self, prompt: str) -> str:
        resp = await self._client.messages.create(
            model=self._model, max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text  # 非 tool 调用，首块即 text
```

### 7.3 CoordinatorRun + registry（新建 `coordinator_run.py`）

```python
_active_runs: dict[UUID, "CoordinatorRun"] = {}  # session_id → run（MVP 进程内）

class CoordinatorRegistry:
    def get(self, sid: UUID) -> CoordinatorRun | None: return _active_runs.get(sid)
    def try_reserve(self, sid: UUID, run: CoordinatorRun) -> bool:
        if sid in _active_runs: return False      # 同步，无 await → 原子
        _active_runs[sid] = run; return True
    def release(self, sid: UUID) -> None: _active_runs.pop(sid, None)

@dataclass
class CoordinatorRun:
    run_id: str                  # uuid4().hex[:12]
    session_id: UUID
    _task: asyncio.Task | None = None

    def start(self, orchestrator, on_done, on_error) -> None:
        self._task = asyncio.create_task(self._run(orchestrator, on_done, on_error))

    async def _run(self, orch, on_done, on_error):
        try:
            result = await orch.run()           # → RunResult（ports.py:39）
            await on_done(result)               # 系统消息汇总
        except asyncio.CancelledError:
            raise
        except Exception as exc:                # 兜底，不上抛
            logger.exception("CoordinatorRun 失败 run=%s", self.run_id)
            await on_error(exc)

    async def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
```

### 7.4 ChatService 增量（改 `chat_service.py`）

```python
# __init__ 新增一个依赖：gate（registry 用模块级单例，不进构造器）
def __init__(self, ..., coordinator_gate: CoordinatorGate) -> None:
    ...
    self._gate = coordinator_gate
    self._registry = CoordinatorRegistry()

# _handle_group：在 @mention 分支(已有)之后、mode 分派(已有)之前插入
async def _handle_group(self, session, group, trigger):
    targets = await self._resolve_mentions(trigger.mentions, group)
    if targets:
        for t in targets:                       # ← 现状不动
            async for evt in self._stream_one_agent(...): yield evt
        return

    # ── 新增：模式闸门 ──
    run = self._registry.get(session.id)
    if run is not None:                          # EXECUTION 态
        if self._gate.is_control(trigger.content):
            await self._cancel_coordinator(session, run)
        return                                   # MVP：非 control 忽略
    if self._gate.has_work_intent(trigger.content) and \
       await self._gate.is_decompose(trigger.content, await self._recent_history(session)):
        await self._start_coordinator(session, group, trigger)
        return
    # ── 以下 mode 分派现状不动 ──
    if group.dispatch_mode == DispatchMode.DISCUSSION:
        async for evt in self._discussion.run_discussion(...): yield evt

async def _start_coordinator(self, session, group, trigger):
    run = CoordinatorRun(run_id=uuid4().hex[:12], session_id=session.id)
    if not self._registry.try_reserve(session.id, run):   # 同步占位，先于任何 await
        await self._post_system(session, "已有任务执行中，请等待或发送「取消」")
        return
    try:
        members = [a for mid in group.member_ids
                   if (a := await self._agents.get_by_id(mid))]
        by_name = {a.name: a for a in members}            # C2：async 预解析
        ctx = gather_context(                              # context.py:111 真实签名
            task=trigger.content, workers=list(by_name),
            workspace=session.workspace_path or None,
        )
        planner = SeedPlanner(AnthropicTextLLM(self._anthropic, settings.coordinator_model))
        executor = AgentExecutor(
            resolve_agent=by_name.get, adapter_factory=build_adapter_for_agent,
            session_id=session.id, group_id=group.id,
            workspace=session.workspace_path or None, event_sink=None,
        )
        verifier = MechanicalVerifier(workspace=session.workspace_path or None)
        orch = Orchestrator(planner=planner, executor=executor, verifier=verifier, ctx=ctx)
        run.start(orch,
                  on_done=lambda r: self._on_coord_done(session, r),
                  on_error=lambda e: self._on_coord_error(session, e))
    except Exception as exc:                               # plan 同步异常等
        self._registry.release(session.id)
        await self._post_system(session, f"任务启动失败: {exc}")
```

### 7.5 系统消息落库（复用 `_persist_user_message` 同款模式）

```python
async def _post_system(self, session, content: str) -> None:
    msg = Message(session_id=session.id, role=MessageRole.SYSTEM, content=content)
    await self._messages.save(msg)
    await self._bus.publish(MessageSent(
        session_id=session.id, message_id=msg.id, role="system", content_type="text"))

async def _on_coord_done(self, session, result: RunResult) -> None:
    self._registry.release(session.id)
    await self._post_system(session, result.summary or f"任务结束: {result.reason}")

async def _on_coord_error(self, session, exc: Exception) -> None:
    self._registry.release(session.id)
    await self._post_system(session, f"任务执行失败: {exc}")

async def _cancel_coordinator(self, session, run: CoordinatorRun) -> None:
    await run.cancel()
    self._registry.release(session.id)
    await self._post_system(session, "已取消当前任务（已完成的成果保留）")
```

> `MessageRole.SYSTEM`（enums.py:45，注释"协调者使用"）、`MessageSent`（events/__init__.py:43）
> 均已存在。`role=SYSTEM` 与 `_persist_user_message` 的 `role="user"` 同路径。

### 7.6 DI 三处（改）

ChatService 在三处构造，都要补 `coordinator_gate`（+ ChatService 持 `anthropic` client 供 Planner）：

- `api/deps.py:138`、`api/deps.py:173`
- `api/ws/chat.py:88`

gate client 复用 Selector 同款 settings 路径（`settings.selector_*` 或新增 `coordinator_*`）。

---

## 8. 空值 / 异常值 / 重复值

| 情况 | 处理 |
|------|------|
| 首次 decompose（registry 空） | 正常流程 |
| registry 有 run 但已死（race） | `_on_coord_done/error` 已 release；若残留，下次 get 到的 run `_task.done()` → 当讨论态（可加 done 检测清理） |
| 空 workers | `plan()` 抛 PlanEmptyError → 系统消息 |
| workspace 为空串 | `session.workspace_path or None` → `gather_context(workspace=None)` → `repo_tree=""` |
| 连续两次 decompose | 第二次 `try_reserve` 返 False → 系统消息 |
| gate LLM 返回非 decompose/discuss | 默认 discuss |
| history 为空 | gate 不依赖 history 必填（预滤只看当前消息）；`is_decompose` 可带空 history |

---

## 9. 并发 / 权限 / 状态流转

| 维度 | 规则 |
|------|------|
| **并发** | 同 session 最多 1 active run。`try_reserve` 同步 check+insert，**先于 `gather_context` 等任何 await**——消除 v1 的双 spawn 竞态（§11 勘误 E3）。asyncio 单线程内此段无 await 即原子；标准档跨进程上 Redis 锁 |
| **权限** | CoordinatorRun 读 workspace（只读，context.py `_safe_workspace_path` 限边界）、调 LLM、写内存 events。worker 写文件在 Executor 内（Phase 4 已定）。**不改 Agent 实体**（busy 不做，见 E4） |
| **状态流转** | 任务态由 Orchestrator 单写（FSM 约束，orchestrator.py:110）。会话态 DISCUSSION ⇌ EXECUTION 由 registry 有无 run 表达，ChatService 前门读取 |
| **副作用** | `gather_context` 只读 IO。CoordinatorRun 改内存 events + registry + 落系统消息。`send_and_stream` 自身生命周期不受 CoordinatorRun 影响 |

---

## 10. 实现增量（替换 v1 §10）

| 文件 | 动作 | 说明 |
|------|------|------|
| `selector.py` | **不动** | ← v1 要改 80 行，v2 零改动（回归面归零） |
| `coordinator_gate.py` | 新建 | 预滤 + LLM 二分类 + control，~50 行 |
| `coordinator_run.py` | 新建 | CoordinatorRun + CoordinatorRegistry，~90 行 |
| `text_llm_adapter.py` | 新建 | AnthropicTextLLM，~30 行 |
| `chat_service.py` | 改 | 闸门分支 + `_start_coordinator` + 系统消息辅助，~70 行 |
| `api/deps.py` | 改 | 两处 ChatService 构造注入 gate |
| `api/ws/chat.py` | 改 | 一处 ChatService 构造注入 gate |
| `core/config.py` | 改 | 加 `coordinator_model`（默认 = anthropic + default_model）|
| `tests/test_coordinator_gate.py` | 新建 | 预滤/分类/control/降级 |
| `tests/test_wiring.py` | 新建 | mock TextLLM + fake 协作者全链路 e2e |
| `tests/test_chat_service.py` | 改 | decompose 分支 + cancel + 防重 |

净效果：**回归风险最大的 selector.py 从"改"变"不改"**，6 根接线降 5 根，DI 漏点补全。

---

## 11. 相对 v1 spec 的勘误（为什么重写）

| # | v1 的错误 | 实测真相 | v2 修正 |
|---|----------|---------|---------|
| **E1** | "ChatService 调 `Selector.pick(active_coordinator=...)`" | `Selector.pick` 只在 `discussion_orchestrator.py:109` 调；ChatService 持 `self._discussion`，无 selector | 闸门下沉 ChatService 前门；Selector 零改动 |
| **E2** | `resolve_agent_in_group` 遍历 `group.members[].agent` | `Group` 只有 `member_ids: list[UUID]`（group.py:32），无 members 对象；且 ResolveAgent 是同步而按名查 Agent 是 async | spawn 时 async 预解析 `{name:Agent}`，闭包成同步 `by_name.get` |
| **E3** | §9 称 check+insert 原子，但流程 `gather_context`(await) 在 register 前 | 两并发 decompose 会双 spawn | `try_reserve` 同步占位，先于任何 await |
| **E4** | busy 路由（#5）列入 MVP | Executor 零 busy 写入；Orchestrator 无 Agent 引用无法清 busy；非 control 全忽略使其冗余；@ 短路使其在 Selector 内失效 | 移出 MVP → 标准档；6 根降 5 根 |
| **E5** | gather_context 签名 `(session, handoff, design_doc)` / "给消息文本" | 实际 `gather_context(*, task, workers, workspace=None, ...)`（context.py:111） | ChatService 自拼 task/workers，按真实签名调 |

---

## 关联文档

- [[coordinator-mvp-implementation-plan]] Phase 5 概述
- [[coordinator-dag-driven-design-v2]] §13 接线方案 + §13.5 A1/A2 + §11.9 busy 路由（标准档）
- [[coordinator-subsystem-collaborators]] §11 Selector × Coordinator 边界
