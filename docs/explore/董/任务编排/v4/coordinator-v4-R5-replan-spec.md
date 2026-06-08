# R5 实现规格 — Replan：DAG 手术 + 破坏性确认

> 日期：2026-06-08 | 状态：实现规格（已按收敛后设计方向修正）| 关联：[[coordinator-design-v4]] §8
> 前提：R0+R1+统一路由重写+R4+abort 已完成
> 风险：**大**（Orchestrator 换图 + ChatService dispatch；但每步独立可测）

---

## 0.0 方向修正（2026-06-08，对照收敛后设计）

本规格初稿写在「7 动作 + 无 abort」时代，以下方向已修正，**覆盖**下文相应代码块：

**D1：不按 task_id 转移节点状态——replan = 全新重建，认 workspace 不认节点。**
原设计 `compute_replan_diff` 按 `old_ids ∩ new_ids` 算 kept 并转移 COMPLETED/RUNNING 状态。
但 task_id 是 Planner（LLM）每次现生成的，replan 重分解后 id 全变（§12.1 例子 A→A' 即证），
且 `_handle_replan` 根本没把旧 id 喂给 Planner → kept 恒空，状态转移是死代码。
**真正持久的是 workspace 文件，不是 DAG 节点**。故改为：replan 直接 `build_graph(new_tasks)`
全新全 PENDING，靠 workspace 持久化保证「完成的不白做」（新任务跑起来发现已存在 → 快速
task_complete）。代价：已完成的活会被便宜地重新核验一遍——可接受。
→ §2.3.1 的「step 1 kept 节点状态转移」整段删除；§2.3.2 diff 大幅简化。

**D2：换图前必须先 abort 静默在飞 worker（并发正确性）。**
replan 从 ChatService 调，若此刻有 worker 在飞，drive 任务正 `await executor.run`——
直接换 `self.graph` 会与 drive 的 settle 撞（两个写者）。故：CoordinatorRun.replan 先
`executor.abort` 掉在飞 worker、`await self._task` 等 drive 收尾，**再** spawn
orchestrator.replan 做干净的换图+drive。复用 abort 已建的 `executor.abort`（杀进程，
不带复盘——replan 是重定向不是用户喊停）。

**D3：is_destructive = 旧图有 RUNNING 节点（在飞或 parked）。**
原设计 COMPLETED 也算破坏性。但 (b) 下完成成果不回滚、文件还在，只是「孤立」——
降为**信息通报**（「已完成的 X 成果保留，不再属于新计划」），不阻塞确认。
只有「有活在跑/parked 会被打断」才弹确认。

**已超越**：§2.1（给路由加 replan 动作、`note_text` 字段）已在统一路由重写里做掉——
replan 动作已在 4 动作集（relay/task/replan/done）里，`note_text` 已决定不加。R5 只剩
ChatService dispatch + orchestrator.replan + 简化 diff + CoordinatorRun stash/quiesce。

---

## 0. 目标

执行期用户要求改方案（「改成微服务架构」「别做博客了，做文档站」「后端换成 Go」）→ `decide → replan(requirement)` → Planner 重新分解 → Harness 算 diff → 决定直接换图还是先求确认 → Orchestrator 原子换图 + 续调度。

一句话验收：**用户说「改成微服务架构」，decide 判 replan → Planner 重新分解出新 DAG → diff 发现要 cancel 正在跑的前端 → 群聊发「计划变更将影响：…请确认」→ 用户说「继续」→ Orchestrator 原子换图，cancel 前端，起新 DAG，全程不丢 COMPLETED 节点的成果。**

---

## 1. 现状（要改的东西）

### 1.1 ReactiveRouter — 无 replan action

```python
# reactive_router.py line 31
Action = Literal["respond", "multi", "task", "feed", "done"]
# ← 缺 "replan"

# _parse_payload (line 88-119) — 无 replan 分支
# _tool_schema (line 124-151) — action enum 无 replan
# _build_prompts (line 153-189) — 执行态 prompt 只说 feed/respond/done
```

执行态 prompt 当前内容（line 166-175）：
```python
else:
    wait = ", ".join(state.active_plan.waiting) or "无"
    mode = (
        f"## 当前态：任务执行中（未完成的 step：{wait}）\n"
        "判据：\n"
        "1. 若上一条 agent 消息是某个未完成 step 的可能提问、而这条像在回答它 "
        "→ action=feed, feed_step=该 step_id, answer=用户回答原文\n"
        "2. 否则是闲聊/旁白：该谁回 → respond+who；无需回 → done\n"
        "（本阶段不要返回 task）"
    )
```

**问题**：不区分「回答 worker 的问题」（feed）、「补充约束」（note，R2 加）、「改方案」（replan）。Planner 被提示词禁用 task，但没告诉它可以 replan。

### 1.2 ChatService — 无 replan dispatch

```python
# chat_service.py _handle_group — decide dispatch section
if decision.action == "task":
    await self._start_coordinator(session, group, trigger)
    return
if decision.action in ("respond", "multi"):
    # ...
    return
# done → 静默
# ← 缺 replan 分支
```

### 1.3 Orchestrator — 无 DAG 手术能力

当前 `Orchestrator` 只有 `start`（建图）和 `on_feed`（续跑），没有换图操作。`build_graph` 存在（`dag.py`），`compute_frontier`/`select_dispatchable` 是无状态的纯函数——换新图后天然按新图算 frontier，不需要调度器感知「图换了」。

### 1.4 CoordinatorRun — 无 pending_replan 状态

破坏性 replan 需要等用户确认，中间需要暂存 new_tasks。

---

## 2. 目标态

### 2.1 ReactiveRouter：加 replan action

#### 2.1.1 Action 枚举

```python
# reactive_router.py
Action = Literal["respond", "multi", "task", "feed", "note", "replan", "done"]
# R2 加了 note，R5 加 replan
```

#### 2.1.2 PlannerDecision 加 replan 字段

```python
@dataclass(frozen=True)
class PlannerDecision:
    action: Action
    who: tuple[str, ...] = field(default_factory=tuple)
    feed_step: str | None = None
    answer: str | None = None
    note_text: str | None = None        # R2：note 时填
    replan_requirement: str | None = None  # R5：replan 时填，用户的新需求文本
    reason: str = ""

    @classmethod
    def replan(cls, requirement: str, reason: str = "") -> PlannerDecision:
        return cls(action="replan", replan_requirement=requirement, reason=reason)
```

#### 2.1.3 _parse_payload 加 replan 分支

```python
# 在 feed 分支之后、done 之前
if action == "replan":
    requirement = payload.get("replan_requirement", "") or reason
    if not requirement:
        logger.warning("ReactiveRouter replan 无 requirement，降级 done")
        return PlannerDecision.done("replan: no requirement")
    return PlannerDecision.replan(requirement=requirement, reason=reason)
```

#### 2.1.4 _tool_schema 加 replan action

```python
"action": {
    "type": "string",
    "enum": ["respond", "multi", "task", "feed", "note", "replan", "done"],
    "description": (
        "respond=选一人回复；multi=选多人回复；"
        "task=这是要实际写代码/改文件/跑命令的开发任务；"
        "feed=回答某个正在执行的 step 的提问；"
        "note=执行期补充约束/信息（不改方向，非提问回复）；"
        "replan=改变任务的根本方向/架构/需求（非补充约束，是推翻重来）；"
        "done=无需任何响应"
    ),
},
# ...
"replan_requirement": {
    "type": "string",
    "description": "replan 时填，用户的新需求是什么"
},
```

#### 2.1.5 _build_prompts 执行态加 replan 判据

执行态 prompt（R2 后 `waiting` 字段已删，改用 `steps` 状态列表）：

```python
# _build_prompts — 执行态分支（R5 更新）
if state.active_plan is None:
    # ... 纯对话态不变（含 task 判据）
else:
    # 从 steps 构造状态摘要
    steps_status = _format_steps_status(state.active_plan.steps)
    mode = (
        f"## 当前态：任务执行中\n{steps_status}\n"
        "判据：\n"
        "1. 若用户消息在**改变任务的根本方向/架构/需求**（非补充细节）→ action=replan, "
        "replan_requirement=用户的新需求原文\n"
        "2. 若上一条 agent 消息提出了问题、而这条像在回答它 → action=feed, "
        "feed_step=该 step_id, answer=用户回答原文\n"
        "3. 若用户消息是**执行期补充约束/信息**（不改方向，如「注意用 React」）→ action=note\n"
        "4. 否则是闲聊/旁白：该谁回 → respond+who；无需回 → done\n"
        "replan 的信号：不是继续对话、不是补充约束，而是推翻重来——"
        "「改成微服务」「别做博客了做文档站」「后端换成 Go」「整体架构重来」。"
    )
```

辅助函数：

```python
def _format_steps_status(steps: tuple[StepView, ...]) -> str:
    """DAG 状态摘要，喂给 decide prompt。"""
    if not steps:
        return "（无任务）"
    lines = []
    for s in steps:
        emoji = {
            "pending": "⏳", "running": "🔄", "verifying": "🔍",
            "completed": "✅", "failed": "❌", "blocked": "⛔", "cancelled": "🚫",
        }.get(s.status, "❓")
        lines.append(f"  {emoji} {s.step_id}（{s.worker}）：{s.status}")
    return "\n".join(lines)
```

### 2.2 ChatService：replan dispatch + 破坏性确认

`_handle_group` 新增 replan dispatch：

```python
if decision.action == "replan":
    if run is None:
        # 纯对话态误判 replan（无 active_plan），降级 task
        logger.warning("replan 误判（无 run），降级 task")
        await self._start_coordinator(session, group, trigger)
        return

    await self._handle_replan(
        session=session, group=group, run=run,
        requirement=decision.replan_requirement,
    )
    return
```

`_handle_replan` 实现：

```python
async def _handle_replan(
    self,
    *,
    session: Session,
    group: Group,
    run: CoordinatorRun,
    requirement: str,
) -> None:
    """执行 replan：重分解 → diff → 破坏性确认/直接换图。"""

    # 1. 构造 replan 上下文
    orchestrator = run.orchestrator
    if orchestrator is None or orchestrator.graph is None:
        return

    original_task = orchestrator._ctx.task  # 原始任务描述（_ctx 是 Orchestrator 公开字段）
    members = await self._group_members(group)

    replan_ctx = PlanContext(
        task=f"原始任务：{original_task}\n\n用户新需求：{requirement}",
        workers=orchestrator._ctx.workers,
        repo_tree=orchestrator._ctx.repo_tree,
        constraints=orchestrator._ctx.constraints,
        agents_desc=orchestrator._ctx.agents_desc,
        # design_doc 不传（replan 是修改，不是从零开始）
    )

    # 2. 重新分解（deliberate 重 LLM）
    try:
        new_tasks = await orchestrator._planner.plan(replan_ctx)
    except Exception as exc:
        logger.exception("replan 分解失败")
        await self._post_system_sync(session, f"计划变更失败：{exc}")
        return

    # 3. diff（Harness 确定性，零 LLM）
    diff = compute_replan_diff(new_tasks, orchestrator.graph)

    # 4. 破坏性？
    if diff.is_destructive:
        # 群聊发确认请求
        await self._post_system_sync(
            session,
            _format_replan_confirmation(diff, requirement),
        )
        # 暂存待确认
        run.stash_replan(requirement, new_tasks, diff)
        logger.info(
            "replan 破坏性，等待确认 session=%s affected_completed=%s affected_running=%s",
            session.id, diff.affected_completed, diff.affected_running,
        )
        return

    # 5. 纯新增/只改 PENDING → 直接换图
    await orchestrator.replan(new_tasks, diff)
    await self._post_system_sync(
        session,
        f"✅ 计划已更新：新增 {len(diff.added)} 项，"
        f"移除 {len(diff.removed)} 项，保留 {len(diff.kept)} 项。",
    )
    logger.info(
        "replan 非破坏性，直接换图 session=%s added=%s removed=%s",
        session.id, diff.added, diff.removed,
    )
```

#### 2.2.1 破坏性确认的接收

用户确认不走 decide（零 LLM 机械反射，跟 control 同级）：

```python
# _handle_group — 在 decide 之前（与 @mention/control/broadcast 同级）
# 前门反射④：pending replan 确认
if run is not None and run.pending_replan is not None:
    if _is_confirmation(text):
        await self._execute_pending_replan(session, run)
        return
    # 不是确认→不清除、不吞消息。
    # fall through 到 decide——用户可能在改需求
    # （「不不，改成 monorepo 架构」），让 LLM 判断下一步。
    # 下一轮 decide 若出 replan，_handle_replan 会覆盖 stash 的新计划；
    # 若出 done/respond/feed 等其他 action，pending_replan 自然留下等
    # 用户后续确认（不急着清——用户可能在闲聊两句后再回来说「继续」）。
```

`_is_confirmation` 纯文本匹配：

```python
_CONFIRM_RE = re.compile(
    # 确认词在开头，后面跟什么都当确认——中文 \b 不可靠（依赖 \w，中文不匹配）。
    r"^(继续|确认|行|可以|ok|yes|好|嗯|对|搞|干|做|没问题|来吧|开始|执行|没错|没错没错|是的|对的|同意|okay|OK|当然|没问题呀)[\s\S]*$",
    re.IGNORECASE,
)

@staticmethod
def _is_confirmation(text: str) -> bool:
    return bool(_CONFIRM_RE.match(text.strip()))
```

`_execute_pending_replan`：

```python
async def _execute_pending_replan(self, session: Session, run: CoordinatorRun) -> None:
    """执行暂存的破坏性 replan。"""
    pending = run.pending_replan
    if pending is None:
        return
    try:
        await run.replan(pending.new_tasks, pending.diff, force=True)
        await self._post_system_sync(
            session,
            f"✅ 计划已变更：{pending.requirement}。"
            f"新增 {len(pending.diff.added)} 项，"
            f"移除 {len(pending.diff.removed)} 项。",
        )
    except Exception as exc:
        logger.exception("replan 执行失败")
        await self._post_system_sync(session, f"计划变更执行失败：{exc}")
    finally:
        run.clear_pending_replan()
```

### 2.3 Orchestrator：DAG 手术

#### 2.3.1 `replan()` 方法

```python
# orchestrator.py
async def replan(
    self,
    new_tasks: list[TaskDef],
    diff: ReplanDiff,
    *,
    force: bool = False,
) -> None:
    """DAG 手术：原子换图 + 续调度。

    force=False：纯新增/只改 PENDING → 直接换。
    force=True：用户已确认破坏性操作（cancel RUNNING / 丢 COMPLETED 成果）。
    """
    if diff.is_destructive and not force:
        raise ReplanNeedsConfirmation(diff)

    old_graph = self.graph
    new_graph = build_graph(new_tasks, set(self._ctx.workers))

    # 1. 转移 kept 节点的运行态数据到新图（design §8.3 铁律）
    for tid in diff.kept:
        old_node = old_graph.nodes.get(tid)
        new_node = new_graph.nodes.get(tid)
        if old_node is None or new_node is None:
            continue
        # worker/dipatch_count 在所有状态都转移（build_graph 不设默认值）
        new_node.worker = old_node.worker
        new_node.dispatch_count = old_node.dispatch_count
        if old_node.status == TaskStatus.COMPLETED:
            new_node.status = TaskStatus.COMPLETED
            new_node.output = old_node.output
        elif old_node.status == TaskStatus.RUNNING:
            new_node.status = TaskStatus.RUNNING
            new_node.pending_answer = old_node.pending_answer
            new_node.pending_notes = old_node.pending_notes
        elif old_node.status == TaskStatus.FAILED:
            new_node.status = TaskStatus.FAILED
            new_node.fail_reason = old_node.fail_reason
            new_node.retries = old_node.retries
        # PENDING/BLOCKED → 保持默认 PENDING（build_graph 已设），不额外处理

    # 2. cancel 受影响的 RUNNING 节点
    # 这些节点在新图中不存在（removed），cancel 是记录到旧图供事件溯源（旧图即将丢弃）。
    # V0 MVP：worker 进程大概率已结束（park 态），cancel 只写日志。
    # 标准档：需 send SIGTERM 给活跃 worker session——此时应 cancel worker 再换图（先杀后换）。
    if diff.affected_running:
        logger.info(
            "replan 丢弃 RUNNING 节点: %s（V0 MVP 仅日志；标准档需 SIGTERM）",
            diff.affected_running,
        )
        for tid in diff.affected_running:
            old_node = old_graph.nodes.get(tid)
            if old_node:
                old_node.status = TaskStatus.CANCELLED
                self._record("cancelled_by_replan", tid)

    # 3. 原子换图
    self.graph = new_graph

    self._record(
        "replan",
        "",
        added=diff.added,
        removed=diff.removed,
        kept=diff.kept,
        affected_completed=diff.affected_completed,
        affected_running=diff.affected_running,
    )

    # 5. 通报（R4 message_sink 已接线，走 _post_message）
    await self._post_plan()
    for tid in diff.affected_running:
        logger.info("replan cancel RUNNING 节点 %s", tid)

    # 6. 恢复调度：按新图算 frontier → 派发
    await self._drive()
```

**铁律**（design-v4 §8.3）：
- COMPLETED 节点成果不回滚（保留 `status` + `output`）
- RUNNING 节点（park 等 feed）不中断（保留 `status` + `pending_answer` + `pending_notes`）
- FAILED 节点不复活（保留 `status` + `fail_reason` + `retries`）
- 受影响的 RUNNING 节点（不在新图）cancel——V0 日志级，标准档先 SIGTERM 后换图
- 原子换图：`self.graph = new_graph`
- `_drive` 不需要感知「图换了」——`compute_frontier` 读的是 `self.graph`，换图后自然按新 DAG 排

#### 2.3.2 diff 纯函数（模块级，可单测）

```python
# orchestrator.py（模块级纯函数，或 orchestrator._diff_replan 内部方法）

@dataclass(frozen=True)
class ReplanDiff:
    added: list[str]       # 新图有、旧图无的 task_id
    removed: list[str]     # 旧图有、新图无的 task_id
    kept: list[str]        # 两图都有的 task_id
    affected_completed: list[str]  # 被 remove 且旧状态=COMPLETED
    affected_running: list[str]    # 被 remove 且旧状态=RUNNING

    @property
    def is_destructive(self) -> bool:
        """破坏性：要 cancel RUNNING / 丢 COMPLETED 成果。"""
        return bool(self.affected_completed or self.affected_running)


def compute_replan_diff(
    new_tasks: list[TaskDef],
    old_graph: TaskGraph,
) -> ReplanDiff:
    """确定性算影响面（零 LLM）。"""
    old_ids = set(old_graph.nodes.keys())
    new_ids = {t.id for t in new_tasks}
    kept = sorted(old_ids & new_ids)
    removed = sorted(old_ids - new_ids)
    added = sorted(new_ids - old_ids)
    return ReplanDiff(
        added=added,
        removed=removed,
        kept=kept,
        affected_completed=[
            tid for tid in removed
            if old_graph.nodes[tid].status == TaskStatus.COMPLETED
        ],
        affected_running=[
            tid for tid in removed
            if old_graph.nodes[tid].status == TaskStatus.RUNNING
        ],
    )
```

#### 2.3.3 `_check_terminal` 更新

换图后 `_drive` → `_check_terminal` 可能遇到：
- 新增节点 PENDING → 正常续派
- 所有节点 COMPLETED → `_finish`
- 无 ready 可派 + 有 PARK 节点 → 休眠等 feed

现有 `_check_terminal` 逻辑不变——它读的是 `self.graph`，换图后自然按新图判断。

### 2.4 CoordinatorRun：stash/clear pending_replan

```python
# coordinator_run.py

@dataclass(frozen=True)
class PendingReplan:
    requirement: str
    new_tasks: list  # TaskDef[]
    diff: ReplanDiff


class CoordinatorRun:
    def __init__(self, session_id: UUID):
        # ... 现有字段 ...
        self.pending_replan: PendingReplan | None = None

    # ── Replan 公开 API（ChatService 不挖 _orchestrator 私有字段）───────

    @property
    def orchestrator(self) -> Orchestrator | None:
        """Orchestrator 引用（公开只读，供 replan diff/执行）。"""
        return self._orchestrator

    async def replan(self, new_tasks: list, diff: ReplanDiff, *, force: bool = False) -> None:
        """转发到 Orchestrator.replan()。ChatService 通过此入口执行 replan。"""
        if self._orchestrator is None:
            raise RuntimeError("无活跃 Orchestrator")
        await self._orchestrator.replan(new_tasks, diff, force=force)

    def stash_replan(
        self, requirement: str, new_tasks: list, diff: ReplanDiff
    ) -> None:
        """暂存 replan 待用户确认。（破坏性 replan 必经此路）"""
        self.pending_replan = PendingReplan(
            requirement=requirement, new_tasks=new_tasks, diff=diff
        )

    def clear_pending_replan(self) -> None:
        self.pending_replan = None
```

### 2.5 确认消息文案

```python
def _format_replan_confirmation(diff: ReplanDiff, requirement: str) -> str:
    """构造破坏性 replan 的确认消息。"""
    lines = [
        f"⚠️ 计划变更「{requirement}」将产生以下影响：",
        "",
    ]
    if diff.affected_running:
        lines.append(
            f"- 正在执行的任务将取消：{', '.join(diff.affected_running)}"
        )
    if diff.affected_completed:
        lines.append(
            f"- 已完成任务可能不再适用：{', '.join(diff.affected_completed)}"
        )
    if diff.added:
        lines.append(f"- 新增任务：{', '.join(diff.added)}")
    if diff.removed:
        lines.append(f"- 移除任务：{', '.join(diff.removed)}")
    lines.extend(["", "请回复「继续」确认变更，或回复其他内容取消。"])
    return "\n".join(lines)
```

---

## 3. 与 replan/feed/note 的边界（design-v4 §8.4）

| 用户说了什么 | decide 判什么 | 为什么 |
|-------------|-------------|--------|
| 「用 Markdown」 | `feed(前端)` | 在跟小美对话，回答她的问题 |
| 「注意用 React」 | `note(who="前端")` | 补充约束，不改方向 |
| 「别做博客了，做文档站」 | `replan` | 根本性需求变更 |
| 「整体架构改成微服务」 | `replan` | DAG 结构要变 |
| 「后端换成 Go」 | `replan` | 可能影响已完成的后端节点 |

**distinguish 提示词要点**：

- `feed`：用户继续跟 worker 对话——接她的话、回答她的提问。即使提了技术选择（「用 Markdown」），本质还是在回答她的对话。
- `note`：不继续对话，也非推翻重来——「注意 React」「顺便加个暗色模式」——补充约束，不改 DAG。
- `replan`：推翻重来——不是继续对话、不是补充细节——「别做博客了」「整体架构重来」「后端换 Go」。DAG 结构要变。

---

## 4. 代码变动清单

| 文件 | 变 | 不变 |
|------|-----|------|
| `reactive_router.py` | `Action` 加 `"replan"`；`PlannerDecision` 加 `replan_requirement` + `replan()` 工厂；`_parse_payload` 加 replan 分支；`_tool_schema` 加 replan + replan_requirement；`_build_prompts` 执行态加 replan 判据 + steps 状态格式化 | respond/multi/task/feed/note/done 分支；降级逻辑 |
| `chat_service.py` | `_handle_group` 加 replan dispatch + pending replan 确认 check + `_is_confirmation`；新方法 `_handle_replan`、`_execute_pending_replan` | @mention/control/broadcast 反射；其余 dispatch 分支 |
| `orchestrator.py` | 新方法 `replan(new_tasks, diff, *, force)`；模块级 `compute_replan_diff()` + `ReplanDiff` dataclass | `start`/`on_feed`/`_drive`/`_check_terminal`/`_finish`/`_settle` |
| `coordinator_run.py` | `PendingReplan` dataclass；`CoordinatorRun` 加 `pending_replan` + `stash_replan` + `clear_pending_replan` | `start`/`on_feed`/`cancel`/`_spawn` |
| `ports.py` | 不用改——`Planner.plan` 已接受 `PlanContext`，replan 复用同一接口 | — |
| `planner.py` | 不用改——`SeedPlanner.plan(ctx)` 通用，replan 上下文通过 `PlanContext.task` 字段传入 | — |
| `dag.py` | 不用改——`build_graph` 通用 | — |

---

## 5. 测试

### 5.1 ReactiveRouter 测试

| 测试 | 验证 |
|------|------|
| `test_replan_action_parsed` | payload `{"action":"replan","replan_requirement":"改成微服务"}` → `PlannerDecision(action="replan", replan_requirement="改成微服务")` |
| `test_replan_no_requirement_downgrades_to_done` | payload 无 requirement → `done` |
| `test_execution_prompt_contains_replan_guidance` | `_build_prompts` 执行态输出含 replan 判据 |

### 5.2 diff 测试

| 测试 | 验证 |
|------|------|
| `test_diff_pure_addition_not_destructive` | 新图只加节点 → `is_destructive=False` |
| `test_diff_remove_pending_not_destructive` | 删 PENDING 节点 → `is_destructive=False` |
| `test_diff_remove_running_is_destructive` | 删 RUNNING 节点 → `is_destructive=True` |
| `test_diff_remove_completed_is_destructive` | 删 COMPLETED 节点 → `is_destructive=True` |
| `test_diff_kept_completed_preserved` | 旧图 A COMPLETED、新图 A 仍在 → kept |

### 5.3 replan 方法测试

| 测试 | 验证 |
|------|------|
| `test_replan_non_destructive_swaps_graph` | 非破坏性 diff → `replan()` 换图成功，COMPLETED 节点保留 |
| `test_replan_kept_running_preserves_pending_answer` | kept 节点旧状态 RUNNING + pending_answer="用 React" → 换图后仍 RUNNING，pending_answer 保留 |
| `test_replan_kept_failed_not_resurrected` | kept 节点旧状态 FAILED + retries=3 → 换图后仍 FAILED，不被复活 |
| `test_replan_destructive_without_force_raises` | `is_destructive=True, force=False` → `ReplanNeedsConfirmation` |
| `test_replan_destructive_with_force_cancels_running` | `force=True` → RUNNING 节点 CANCELLED，新图就位 |
| `test_replan_resumes_scheduling` | `replan()` 后 `_drive` 派新图的 PENDING 节点 |

### 5.4 ChatService 集成测试

| 测试 | 验证 |
|------|------|
| `test_replan_non_destructive_executes_immediately` | decide→replan，纯新增 → 直接换图 + 群聊通报 |
| `test_replan_destructive_posts_confirmation_and_stashes` | decide→replan，删 RUNNING → 发确认消息 + run.pending_replan 非空 |
| `test_replan_confirmation_executes` | pending_replan 存在 + 用户说「继续」→ replan(force=True) |
| `test_replan_cancelled_by_user` | pending_replan 存在 + 用户说「算了」→ clear + 群聊通报「已取消」 |
| `test_replan_without_run_downgrades_to_task` | 纯对话态误判 replan → 降级 task |

---

## 6. 风险与未决

1. **replan 破坏性确认走零 LLM 机械反射**：`_is_confirmation` 用正则 + 精确字符串集合，不是为了省一次 LLM 调用，而是确认/取消不需要语义理解——用户看到「请确认」后回复「继续」「算了」是二元选择。正则覆盖大部分确认词（`^(继续|确认|行|...)\b`），再加精确集合兜底中文短词（`"好的"`, `"行吧"`, `"搞起"`…）。如果漏了边缘表达（如「安排」），风险可控——漏判最多让消息进 decide，decide 大概率判 done（不命中任何 action）。

2. **replan 期间并发消息的处理**：用户发完「改成微服务」后立刻又发一条。第一条触发 replan + stash + 发确认提示。第二条进 pending_replan 门禁：是确认→执行 replan；不是确认→**fall through 到 decide**，不清除 pending_replan。用户可能在改需求（「不不，改成 monorepo」）→ decide 若再出 replan，覆盖 stash。用户也可能在闲聊→ decide 出 respond/done → pending_replan 自然留存，用户聊完可以回来说「继续」确认。不主动清除——pending_replan 只在成功执行或显式取消时清。

3. **replan 后 graph 引用的线程安全**：V0 MVP 串行调度，不存在并发问题。标准档开并发后 `replan()` 需要原子性保证（在暂停调度后再换图——已在 `replan()` 实现中体现：只在方法内换 `self.graph`，无 async 让出点）。

4. **Worker cancel 的完整性**：V0 MVP worker 是短驻 CLI（流结束即进程退出），`affected_running` 节点大概率已是 `not_done` park 态（进程已结束，逻辑仍在 RUNNING）。`cancel` 只是记 `CANCELLED` 状态——进程不存在了，不需要 SIGTERM。标准档长驻 CLI 需要补 `cancel_worker_session` 调用。

5. **与 R2 的依赖**：R5 的 `_build_prompts` 执行态分支假设 `PlanView.waiting` 已删（R2），改用 `steps` 状态列表。如果 R2 未做，R5 需要兼容两种 PlanView。实现顺序：R2 先做。

6. **Planner 重分解的质量**：replan 的 `PlanContext.task` 内容为 `"原始任务：{A}\n\n用户新需求：{B}"`。Planner 是否能正确理解「在已有 DAG 基础上改」而非「从零开始」——取决于 prompt 工程。当前 prompt 已含任务描述，加 replan 语义说明即可。如果质量不行，后续可给 Planner 传 DAG 快照文本（结构化状态列表）。

7. **`_post_system_sync` 作用域**：replan 确认消息在 `_handle_group` 请求作用域内用 `_post_system_sync` 写（复用请求的 repo/bus），与 R4 Orchestrator 后台路径的 `post_system_background`（独立 DB session）不同。此处正确——replan 的 Planner.plan + diff + 消息落库在同一个请求内完成，请求 scope 的 repo/bus 有效。`_execute_pending_replan`（确认后执行）同理——用户确认请求内完成 replan。无需改。

---

## 7. 不碰的部分

| 保留项 | 原因 |
|--------|------|
| `Planner.plan(ctx)` 接口 | 通用，replan 只构造不同 ctx |
| `build_graph` / `scheduler` 函数 | 纯函数，换图后自然生效 |
| `_settle` / `_finish` / `_check_terminal` | 读 `self.graph`，换图后自动反映新状态 |
| `_drive` 事件驱动循环 | 不需要感知「图换了」 |
| `_emit_update` / `_emit_plan` (progress) | 不变 |
| `_post_message` (R4 message_sink) | 不变，replan 通报走同一通道 |
| `CoordinatorRegistry` | run 生命周期不变 |

---

## 8. 实现记录

> 实现日期：2026-06-08 | 状态：已实现，258 passed（2 pi_agent 预存失败无关）
> 按 §0.0 方向修正实现，**不是**本规格 §2.3 初稿的 id-diff 版。

### 实际实现（对照 §0.0）

- **D1 认 workspace 不认节点**：`ReplanDiff` 只读旧图状态（running/completed/new_count），
  **不按 id 匹配、不转移节点状态**。`replan()` 直接 `build_graph(new_tasks)` 全新全 PENDING。
  `plan_replan()` 把已完成节点的 output 喂进 Planner prompt（「成果在 workspace，勿重做」）。
- **D2 换图前静默**：`CoordinatorRun.replan` → `_quiesce()`（`orchestrator.abort_inflight()`
  杀在飞 worker + `await self._task` 等 drive 收尾）→ 再 spawn `orchestrator.replan`。
  `orchestrator.replan` 假设无在飞，干净换图。
- **D3 running 才破坏性**：`is_destructive = bool(running)`。completed 仅进确认文案的信息行
  （「成果保留，不再属于新计划」），不阻塞。
- **复用 abort**：`abort_inflight` 用已建的 `executor.abort`（杀进程，不带复盘）。

### 改动文件

| 文件 | 改动 |
|------|------|
| `orchestrator.py` | `ReplanDiff` + `ReplanNeedsConfirmationError` + `compute_replan_diff`（简化版）；`abort_inflight` / `plan_replan` / `replan` 方法 |
| `coordinator_run.py` | `PendingReplan`；`pending_replan` 字段；`orchestrator` 公开属性；`plan_replan`/`stash_replan`/`clear_pending_replan`/`replan`/`_quiesce` |
| `chat_service.py` | `_CONFIRM_RE`/`_is_confirmation`；确认反射（control 同级）；replan dispatch 替换 interim stub 为 `_handle_replan`；`_format_replan_confirmation` |

### 与初稿规格的偏离（已被 §0.0 覆盖，此处汇总）

- `compute_replan_diff` 签名/语义全改（不再 added/removed/kept by id）。
- `orchestrator.replan` 删掉「kept 节点状态转移」整段。
- `ReplanNeedsConfirmation` → `ReplanNeedsConfirmationError`（N818 命名规范）。
- 异常实际不在正常路径抛（chat_service 先用 `diff.is_destructive` 决策；它是 force 误用的安全网）。

### 未决 / 边角

- **M2「继续」歧义**：pending_replan 待确认 + parked worker 都可能被「继续」命中——前门反射
  优先吃成 replan 确认。低频，已知限制（确认窗口期用户通常就是在回应 replan）。
- **pending_replan 不主动清**：非确认消息 fall-through 到 decide，pending 留存等后续确认或被
  新 replan 覆盖。可能 stale（用户走神），接受。
- **abort_inflight 在并发档**：MVP 串行只有一个在飞；标准档多 worker 时会 abort 全部 running——
  符合「换图前全静默」语义。

### 测试

- `test_orchestrator_replan.py`（7）：diff 语义、破坏性 raise、换图全新、force 换、plan_replan 喂
  requirement+已完成、abort_inflight 只杀 running。
- `test_chat_service.py` +3：replan 非破坏直接换 / 破坏暂存待确认 / 确认反射 force 执行。
