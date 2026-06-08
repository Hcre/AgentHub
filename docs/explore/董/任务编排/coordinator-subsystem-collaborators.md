# Coordinator 子系统 — 协作者分解与协作模型

> 日期：2026-06-05 | 状态：设计稿（§6 工具/上下文标「讨论中」）
> 配套：[[coordinator-dag-driven-design-v2]]（v2.3，确定性逻辑细节）、[[coordinator-test-plan]]
> 本文回答：Coordinator 该不该扛这么多职责？拆成什么？怎么协作？谁是 LLM 谁是代码？

---

## 1. 核心重构：Coordinator 是子系统，不是一个组件

把所有职责挂在"协调者"一个名字下 = god object。盘点后它扛了约 20 项活（见 §4），单个组件扛不动。

**结论：Coordinator 不该是一个类，是一个子系统**——拆成 5 个聚焦协作者 + 已有的 Selector。每个单一职责，无 god object。

```
  用户消息 → Selector ──decompose──→ ┌─────────────────────────────┐
                  │                   │   Orchestrator              │
                  └─discussion        │   单写者事件循环（代码）      │
                                      │   · 唯一改状态 + 写 task_events│
                                      └──┬────┬────┬────┬────┬───────┘
                          调用 ↓        ↓    ↓ 派发 ↓ 验证 ↓ 发射
                       Planner    Scheduler Executor Verifier EventBus→WS
                      (LLM 推理)   (纯函数)  (worker  (验收     (前端进度)
                                            生命周期) 闸门)
```

---

## 2. 谁是 LLM/CLI，谁是代码（最关键的澄清）

**误区**：把 Orchestrator 当成"有工具、靠 JSON 决定调谁"的 agent。**它不是。**

**Orchestrator 是普通代码**（事件循环），调谁靠写死的 `match event` 分支，不是 LLM 看 JSON 决定。

| 角色 | 是 LLM/CLI 吗 | 怎么被调用 |
|------|:---:|------|
| **Orchestrator** | ❌ 代码 | 是它调别人 |
| **Scheduler** | ❌ 纯函数 | `compute_frontier(graph)` |
| **Planner** | ✅ **LLM** | `await planner.plan(ctx)`，**内部**才调 LLM |
| **Executor** | ❌ 代码 | `executor.dispatch(t)`，内部起 worker CLI |
| **Verifier** | ❌ 代码 | `await verifier.verify(t)`，内部跑命令 |
| **Worker** | ✅ **CLI** | 由 Executor 起 |

**整个系统只有 Planner 和 Worker 背后是 LLM/CLI，其余全是代码，互相用普通函数调用。**
**JSON 只出现在一处**：Planner 内部把 LLM 输出解析成 `TaskDef`——不是"决定调谁"，是"解析计划内容"。

---

## 3. 协作模型：Orchestrator 单写者指挥 + 三条铁律

| 协作者 | 能做 | 不能做 |
|--------|------|--------|
| **Orchestrator** | 改 FSM 状态、写 task_events、调所有人、判退出 | —（唯一写者） |
| **Scheduler** | 读 graph 算就绪集 | 改状态 |
| **Planner** | 读上下文出计划/裁决 | 改状态、碰编排 |
| **Executor** | 派 worker、盯活、隔离 | 改 graph 状态（只 emit 事件） |
| **Verifier** | 跑验收命令、出 verdict | 改状态（只返回 pass/fail） |

**Executor/Verifier 干完活只"汇报"，由 Orchestrator 落状态——这就是单写者，无竞态。**

---

## 4. 职责归属表（约 20 项 → owner）

| # | 职责 | owner |
|---|------|-------|
| 1 | 分解任务 → DAG（facts + plan） | Planner |
| 2 | 失败 replan（子树作用域） | Planner |
| 3 | 动态扩图 | Planner |
| 4 | 里程碑回顾（汇聚点） | Planner |
| 5 | final_answer 综合 | Planner |
| 6 | 读仓库取 facts（agentic 时） | Planner（标准）/ Orchestrator 代码（MVP，见 §6） |
| 7 | 构建/校验 DAG | Scheduler |
| 8 | 算 frontier | Scheduler |
| 9 | 派发 worker（并发上限） | Executor + Scheduler(选) |
| 10 | 驱动 FSM 状态转移 | Orchestrator |
| 11 | 单写者事件循环 + 事件溯源 | Orchestrator |
| 12 | worker 卡死检测 | Executor |
| 13 | 验证闸门（机械 + reviewer） | Verifier |
| 14 | worktree 管理（建/merge/冲突） | Executor + Orchestrator(merge) |
| 15 | 集成验证（全量测试） | Verifier |
| 16 | 退出条件 / 预算管控 | Orchestrator |
| 17 | 进度推前端 | Orchestrator → EventBus |
| 18 | 用户插话分类 | Selector |
| 19 | 从 DAG 状态机械回答提问 | Orchestrator |
| 20 | 审批闸门（external） | Verifier/Orchestrator + 人 |

---

## 5. 各协作者接口与调用方式

### 5.1 Orchestrator（指挥，代码）

```python
class Orchestrator:                       # ← 普通代码，不是 LLM
    def __init__(self, planner, executor, verifier):
        self.planner, self.executor, self.verifier = planner, executor, verifier

    async def run(self, task_text):
        ctx = self.gather_context(task_text)             # §6
        task_defs = await self.planner.plan(ctx)         # 调 Planner = await 方法
        self.graph = build_graph(task_defs, self.workers)  # Scheduler 纯函数
        self.dispatch_frontier()

        async for event in self.bus:        # 事件循环
            match event:                    # 调谁是写死的分支，不是 LLM 决定
                case WorkerDone(t):
                    await self.settle(t); self.dispatch_frontier()
                case WorkerFailed(t):
                    self.handle_failure(t)
                case WorkerTimeout(t) | WorkerLoop(t):
                    self.handle_failure(t)
                case UserInterrupt(msg):
                    self.handle_interrupt(msg)
            if self.all_done():
                return await self.planner.final_answer(self.graph)

    def dispatch_frontier(self):
        ready = compute_frontier(self.graph)             # Scheduler
        for tid in select_dispatchable(ready, running=self.running, max_concurrency=1):
            self.transition(tid, RUNNING)                # 自己改状态（单写者）
            self.executor.dispatch(self.graph.nodes[tid])

    async def settle(self, t):
        self.transition(t, VERIFYING)
        verdict = await self.verifier.verify(t)          # Verifier 返回 pass/fail
        if verdict.passed: self.transition(t, COMPLETED)
        else: self.bus.emit(WorkerFailed(t))
```

### 5.2 Planner（推理，唯一 LLM 协作者）

```python
class Planner:
    def __init__(self, llm):              # llm 适配器：MVP=API，标准=CLI
        self.llm = llm

    async def plan(self, ctx) -> list[TaskDef]:
        raw = await self.llm.chat_structured(build_plan_prompt(ctx))  # ← 唯一 LLM 调用
        return parse_task_defs(raw)                                    # JSON→TaskDef 容错解析
```

**Planner 无状态**——不维护跨调用上下文。每次调用 Orchestrator 现场组装 ctx（来源 §5.2.1）。

#### 5.2.1 上下文从哪来（不用单独维护）

| Planner 调用 | ctx 来源（Orchestrator 现场组装） |
|-------------|-------------------------------|
| `plan` | 任务文本 + 仓库目录树 + Agent 注册表 + 交接约束 + 用户文档 |
| `replan` | 失败子树：失败任务全文 + 依赖 + 下游 + 其余仅标题（v2 §4.1） |
| `review` | 上游摘要 + 约束清单 |
| `final_answer` | 所有任务摘要 + 集成结果 |

**真相源是 DAG 状态 + task_events（Orchestrator 已维护）**；Planner 看到的工作上下文每次现算，不单独存。标准档 CLI 自己那点内部上下文活在单次调用内、用完即弃。**→ "协调者要不要维护上下文"基本消解。**

#### 5.2.2 Planner 的两种交付形态

| | 形态 | 工具 | 何时 |
|---|---|---|---|
| 裸结构化 API（`chat_structured`，上下文预注入）| LLM 无工具 | 简单好测 | **MVP** |
| 一次性 CLI session（探仓库 → `submit_plan` 吐 JSON）| CLI 原生只读工具 | 自适应探索 | **标准** |

两者都是"调适配器拿结构化 dict"，是**一次性调用**（起会话→拿结果→结束），不常驻。

### 5.3 Scheduler（纯函数）— 已建（dag.py / scheduler.py）

`compute_frontier(graph)` / `unreachable_pending(graph)` / `select_dispatchable(...)`。纯查询，不改状态。

### 5.4 Executor（代码，内部起 worker CLI）

```python
class Executor:
    def dispatch(self, node):
        session = self.cli.start(node.task.instruction, worktree=node.worktree)  # worker CLI
        asyncio.create_task(self._pump(node, session))  # worker 流 → 事件 emit
    # 看门狗：心跳/超时/重复 → emit WorkerTimeout/WorkerLoop（机械，零 LLM）
```

### 5.5 Verifier（代码，内部跑命令）

```python
class Verifier:
    async def verify(self, node) -> Verdict:
        for check in node.task.acceptance:
            if check.kind == "mechanical":
                if await run_command(check.spec, cwd=node.worktree) != 0:
                    return Verdict(passed=False, reason=...)
        return Verdict(passed=True)        # 只出裁决，不改状态
```

---

## 6. 上下文与工具（主决策已定 ✅）

> 核心决策已定（§6.8）：标准档 Planner = 种子（程序注入目录树）+ 方案① 只读 tool_use 循环。
> 仅剩一个小遗留：`workspace_path` 的初始化配置流（§6.2 末），属项目接入 UX，不挡协调者。
> 逻辑链：为什么读 → 读哪个目录 → 固定读什么（种子）→ 弹性怎么补 → 三方案对比 → 落地示例。

### 6.1 为什么需要读文件 —— 把"猜"变成"事实"

Planner 要产出好的 TaskDef（depends_on / suggested_worker / acceptance），得回答一堆**关于真实仓库**的问题：

| 分解时要回答 | 不读会怎样 |
|-------------|----------|
| 已有 auth 模块吗？create 还是 modify？ | 重复造 / 改错地方 |
| 文件放哪？目录约定？ | **路径错** |
| 技术栈 React/Vue？ | 任务指令写错框架 |
| 现有 User 模型/schema？ | 后端任务和现有 model 对不上 → 执行失败 |
| 测试/构建命令？ | **acceptance 写不出来** |
| 有哪些 Agent、能力？ | suggested_worker 指向不存在的 Agent |

**不读 = 基于假设分解，假设错 → 执行撞现实失败（MAST 41.77% 的"规格模糊"）。读 = 把假设变事实。** 深度随任务：绿地（从零）目录树够；棕地（改现有码，AgentHub 多数）必须读现有代码。

### 6.2 目录从哪来 —— `Session.workspace_path`（已有概念，非新增）

AgentHub 早有 workspace：

- `protocol.py` `AgentRequest.working_directory` —— "CLI 进程 cwd，宿主机绝对路径"
- `session.py` `Session.workspace_path` —— "Agent 工作目录"
- 三个 CLI 运行时（claude_code/pi_agent/opencode）都从这字段 resolve `cwd`

**Coordinator 读的就是 worker 写的同一个目录**：

```
session.workspace_path ─┬─→ worker CLI 的 cwd（在这改代码）
                        └─→ Coordinator gather_context 读这里（看有什么）
```

列文件机制（机械、零 LLM）：

```python
def list_tree(workspace: str, depth=3) -> str:
    if is_git_repo(workspace):
        files = run("git ls-files", cwd=workspace).splitlines()  # 尊重 .gitignore，只列真实源码
    else:
        files = walk_prune(workspace, ignore=[".git","node_modules",".venv","dist","__pycache__"])
    return build_tree(files, max_depth=depth)
```

> 唯一待明确（小）：`workspace_path` 怎么被设上——会话初始化的配置流（手填/克隆/挂载）。字段已在模型里，Coordinator 只管消费；只要有值就能跑。标准档 worktree 时 worker 在派生 worktree 跑，Planner 读 `workspace_path` 这个 base。

### 6.3 固定读取（种子）—— "已知位置 allowlist"，不判断相关性

`gather_context` 抓一组**可预测、几乎总相关**的东西，逻辑是"去固定地方拿固定东西"，全是 Orchestrator 确定性代码：

```python
class Orchestrator:
    def gather_context(self, task_text, design_doc=None) -> PlanContext:
        ws = self.session.workspace_path
        return PlanContext(
            task        = task_text,                         # 任务 + 约束（永远要）
            constraints = self.handoff.constraints,
            agents      = self.registry.list(),              # 注册表：能派给谁（永远要）
            repo_tree   = list_tree(ws, depth=3),            # 目录树：放哪/有什么
            stack       = read_first_exists(ws, ["package.json","pyproject.toml",
                              "requirements.txt","go.mod","Cargo.toml"]),  # 技术栈
            commands    = discover_commands(ws),             # test/build 命令 → acceptance 来源
            conventions = read_if_exists(ws, ["README.md","CLAUDE.md","AGENTS.md"], max_kb=20),
            design_doc  = read_file(design_doc, summarize_if_over_kb=30) if design_doc else None,
        )
```

**故意不读**：任意源码文件（具体 `models.py`、任务要碰的组件）——读它们要先判断"哪个相关"，那是 §6.4 的弹性问题。**种子里 Planner 零工具。**

### 6.4 弹性三档 —— 不是开关，是档位

固定种子的死穴：碰到"后端必须匹配现有 User 模型"，固定 bundle 要么漏 `models.py` 要么全读爆上下文。按成本三档：

| 档 | 弹性来源 | 成本 | Planner 有工具吗 | 何时 |
|----|---------|------|:---:|------|
| **A 反应式 replan** | plan 错 → 验收失败 → replan（带失败原因再 ground） | 一轮失败+replan | ❌ | **MVP** |
| **B 机械 scout** | plan 前 grep 任务关键词 → 读命中文件注入 | 1 次 grep(+可选 1 LLM 抽词) | ❌ | A 漏太多时 |
| **C agentic** | LLM 自己 Read/Grep 直到有把握 | 整个会话 | ✅ | B 不够时 |

```python
# 档 B 机械 scout
def scout(workspace, task_text) -> list[str]:
    keywords = extract_keywords(task_text)          # "登录" → [login, auth, 登录, user]
    hits = grep_repo(workspace, keywords, top=5)    # 命中 auth.py, models.py(User)
    return [read_file(f, max_kb=10) for f in hits]
```

**关键洞察**：A、B 两档 Planner **零工具**（弹性靠 Orchestrator 代码：replan 循环 / grep）；**只有 C 给 Planner 工具**。多数情况 B 就够。

### 6.5 三方案对比（评估「Harness 工具循环 / CLI 探查 / 固定」）

讨论中提出三个方案。**关键：方案1 和方案2 是同一形状**（LLM 边探边定的 agentic 读循环），区别只在谁执行工具、谁拥有循环；**方案3 是它俩的种子，不是竞品**。

| 维度 | ① Harness 工具循环 | ② CLI 探查器 | ③ 固定编码 |
|------|------------------|------------|----------|
| 工具谁执行 | **我们的只读函数** | CLI 原生 | 无 |
| 循环谁拥有 | 我们（API tool_use，可 bound 轮数） | CLI queryLoop | 无 |
| 弹性 | 高 | 最高（无界） | 低 |
| 成本 | 中（多轮有上限） | 高（整会话） | 最低 |
| 确定性/可测 | **高**（mock LLM 返回 tool_call→submit_plan） | 低（mock 整会话） | 最高 |
| 只读管控 | **天然**（只暴露读工具） | 要配置（CLI 默认能写） | 天然 |
| 实现量 | 小（read/grep 几行 + 复用 tool_use） | 小但要限只读+结构化契约 | 中 |

**判断：对"分解"这个任务（有界 + 只读 + 结构化输出），方案① > 方案②。** 方案② 的额外能力（edit 工具、无界探索、完整上下文压缩）是过剩，反而带来不确定 + 只读管控 + 结构化契约三笔成本。方案① 正好匹配，且 tool 循环是 **API 原生 tool_use**（Selector 已用 `select_next_speaker`），不触发"重造 agent 机制"。

**排序：① 种子+只读 tool_use 循环（最优）> ③ 单独用=MVP floor > ② CLI（过剩，留备选）。**
方案② 只在两种情况更好：分解过程需要 edit/run，或战略上要 Planner 与 Worker 全用 CLI 同构。

### 6.6 落地示例：方案① 怎么作用（"给登录加记住我"）

棕地任务，已有登录页。**种子（§6.3）+ 只读 tool_use 循环（方案①）**：

```
种子: repo_tree 显示 LoginForm.tsx / auth.py / settings.py 存在（但无内容）

Round 1  LLM → read_file("frontend/src/components/LoginForm.tsx")
         [Orchestrator 执行] → "email/password 两输入框，无 remember 字段"
Round 2  LLM → read_file("backend/app/api/auth.py")
         → "签发 JWT，expire 用 settings.JWT_EXPIRE"
Round 3  LLM → grep("JWT_EXPIRE","backend/")
         → "settings.py:12  JWT_EXPIRE = timedelta(minutes=30)"
Round 4  LLM → submit_plan({t1 改 LoginForm 加勾选框, t2 改 auth+settings 时效 30 天, t3 e2e})
         [Orchestrator] 见 submit_plan → 退出，解析 → build_graph
```

驱动代码：

```python
TOOLS = [read_file_tool, grep_tool, list_dir_tool, submit_plan_tool]

class Planner:
    async def plan(self, ctx) -> list[TaskDef]:
        messages = [{"role": "user", "content": build_seed_prompt(ctx)}]
        for _ in range(MAX_ROUNDS):                    # 有界（如 8）
            resp = await self.llm.messages(messages, tools=TOOLS)
            tool = resp.tool_use
            if tool.name == "submit_plan":
                return parse_task_defs(tool.input)     # 结束
            result = self._exec_readonly(tool)         # Harness 执行只读工具
            messages += [assistant(tool), user(tool_result(result))]
        raise PlanBudgetExceeded                       # 兜底 → replan/问人

    def _exec_readonly(self, tool):
        match tool.name:
            case "read_file": return read_file(safe_path(tool.input["path"]), max_kb=20)
            case "grep":      return grep_repo(tool.input["pattern"], tool.input.get("dir","."))
            case "list_dir":  return list_tree(tool.input["path"], depth=2)
        # 无 write/edit/bash —— 物理上改不了文件
```

**这个例子说明**：种子给"文件在哪"、工具读"文件内容"（缺一不可）；只读是物理保证（无 write）；`MAX_ROUNDS` 有界；`submit_plan` 强制结构化；plan 落地真实事实（token 时效在 settings.py）→ 不撞现实失败；可测（mock `[read,read,grep,submit_plan]` 序列）。

对比纯固定（③）：种子无 LoginForm 内容 → LLM 猜结构 → 执行对不上 → replan。方案① 提前读真文件省掉这轮。

### 6.7 用户把计划写在文档里 —— 最干净的预注入场景

用户给的文档是**已知输入**，不用 Planner"发现"，`gather_context` 直接读进来注入（§6.3 的 `design_doc`）：

```
用户: "按这份设计文档实现" + design.md
  → gather_context(task, design_doc="design.md")   read_file 注入   ← 代码读，确定性
  → Planner.plan(ctx)   LLM 读文档计划 → 翻译成结构化 TaskDef
```

这是 v1 的 `FetchDoc`，但**不用做成工具**——已知输入确定性注入即可。
**Planner 的活**：文档给散文版 WHAT，Planner 补 WHO（派哪个 Agent）+ HOW（acceptance）+ ORDER（depends_on），翻译成可执行 DAG。文档大 → 先摘要/分块。

### 6.8 分级映射

| | Planner 形态 | 弹性档 | 工具 |
|---|---|---|---|
| **MVP** | 种子（§6.3）一次 `chat_structured` | A 反应式 replan | ❌ |
| **标准** | 种子 + 方案① 只读 tool_use 循环（§6.5/6.6） | C（受控只读） | ✅ 只读 |
| 中间增强 | 任意档可加档 B scout（§6.4） | B | ❌ |

**✅ 已决（2026-06-05）：标准档 Planner 用方案①**——程序注入目录树（种子）让 Planner 知道有哪些文件 → Planner 用 `read_file`/`grep` 只读工具决定读哪个内容 → 程序执行喂回 → 循环到 `submit_plan`。理由：分解是"有界 + 只读 + 结构化"任务，方案①的控制/可测/天然只读优于方案② CLI 的无界探索（过剩，且带不确定+管控+契约成本）。方案② 仅作"分解需 edit/run 或战略要求 Planner/Worker 全 CLI 同构"时的备选，本设计不采用。

### 6.9 方案① 实现要点（标准档，~40 行 + 安全路径限制）

三个部件，复用 Selector 已有的 Anthropic tool_use 模式（`selector.py` 的 `select_next_speaker`），只是多轮 + 多工具。

**① 工具 schema**：`read_file` / `grep` / `list_dir` / `submit_plan`（Anthropic tools 格式）。前三只读，`submit_plan` 强制结构化输出 TaskDef 数组。

**② RepoReader —— 只读执行器（关键：路径限边界）**

```python
class RepoReader:
    """只读访问 session.workspace_path。无 write/edit/bash —— 物理上改不了。"""
    def __init__(self, workspace: str):
        self.root = os.path.realpath(workspace)

    def read_file(self, path: str, max_kb: int = 20) -> str:
        with open(self._safe(path)) as f:
            return f.read(max_kb * 1024)

    def grep(self, pattern: str, dir: str = ".") -> str:
        return run(["git", "grep", "-n", "-e", pattern, "--", dir], cwd=self.root)

    def list_dir(self, path: str = ".") -> str:
        return list_tree(self._safe(path), depth=2)

    def _safe(self, path: str) -> str:
        """安全红线：防 ../../etc/passwd 路径穿越，锁死在 workspace 内。"""
        full = os.path.realpath(os.path.join(self.root, path))
        if not (full == self.root or full.startswith(self.root + os.sep)):
            raise ValueError(f"越界访问被拒: {path}")
        return full
```

> ⚠️ `_safe` 是**安全红线**——LLM 可能要求读 workspace 外的文件，必须锁死。不能省。

**③ tool_use 循环（标准 Anthropic 多轮）**

```python
class Planner:
    def __init__(self, llm, reader: RepoReader):   # llm=AsyncAnthropic（Selector 同款）
        self.llm, self.reader = llm, reader

    async def plan(self, ctx) -> list[TaskDef]:
        messages = [{"role": "user", "content": build_seed_prompt(ctx)}]   # 种子注入树/注册表/stack
        for _ in range(MAX_ROUNDS):                          # 有界（如 8）
            resp = await self.llm.messages.create(
                model=settings.planner_model, max_tokens=2048,
                messages=messages, tools=PLAN_TOOLS,
                tool_choice={"type": "any"},                 # 强制：要么读，要么 submit_plan
            )
            tu = _first_tool_use(resp)
            if tu.name == "submit_plan":
                return parse_task_defs(tu.input["tasks"])     # → build_graph 校验（已建）
            result = self._exec(tu)                           # 执行只读工具
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tu.id, "content": result}]})
        raise PlanBudgetExceeded                              # 兜底 → replan/问人

    def _exec(self, tu) -> str:
        match tu.name:
            case "read_file": return self.reader.read_file(tu.input["path"])
            case "grep":      return self.reader.grep(tu.input["pattern"], tu.input.get("dir", "."))
            case "list_dir":  return self.reader.list_dir(tu.input.get("path", "."))
```

`messages` 累积对话（assistant tool_use + user tool_result）——"上下文管理"就是 append 到 list，`MAX_ROUNDS` 兜底，分解短不用压缩。

**复用/新建**：

| | 状态 |
|---|------|
| Anthropic tool_use 客户端 | ✅ 复用 Selector 的 `AsyncAnthropic` |
| `workspace_path` / `build_graph` | ✅ 已有 / 已建 |
| RepoReader（只读+限边界）+ PLAN_TOOLS + 循环 | 🔨 新建，~40 行 |

**测试**：mock `llm.messages.create` 返回脚本序列 `[read_file, grep, submit_plan]`，RepoReader 用临时目录真文件 → 确定性可测，不碰真 LLM。

**前提**：这是**标准档**。MVP Planner 不读文件——只种子一次 `chat_structured`，漏的靠 replan（§6.8 档 A）。本循环等需要弹性时再加。

---

## 7. 老问题在新结构里的归属（拆分不发明新解，是给解法定 owner）

| 老问题 | owner | 解了吗 |
|--------|-------|:---:|
| 任务失败 | Executor 报 → Orchestrator 决策 → 重试/replan(Planner) | ✅ |
| 路径错/plan 错 | Orchestrator 汇聚点调 Planner.review → replan | ⚠️ 解，C 类极限：fan-in 时上游已投入 |
| worker 自报说谎 | Verifier 独立裁决，Orchestrator 落状态 | ✅ |
| 卡死 | Executor 看门狗 emit 事件 | ✅ |
| 文件冲突 | Executor worktree 隔离 | ✅ |
| 语义冲突 | Verifier 集成闸门抓可测子集 | ⚠️ 残余 C 类极限 |

C 类极限（语义冲突、plan 错事前不可知）**任何结构都消不掉**，拆分只让每个问题有唯一 owner、可独立测。

---

## 8. 与已建代码的关系

拆分没作废任何东西——已建的 `dag.py`/`scheduler.py`/`fsm.py` **就是 Harness 控制面本体**：

| v2 设计的 | 拆分后叫 | 状态 |
|-----------|---------|------|
| 状态节点循环（PENDING→RUNNING→VERIFYING→COMPLETED） | Orchestrator 驱动 + fsm.py 约束 | ✅ 已建 |
| DAG / frontier 调度 | Scheduler | ✅ 已建（dag/scheduler） |
| §2.2 `coordinate()` 事件循环 | `Orchestrator.run()` | 待建 |
| §6.3 `verify_and_settle` | `Orchestrator.settle()` + `Verifier.verify()` | 待建 |

**拆分 = 给同一个事件循环里的动作起名字，不是重新设计。**

---

## 9. 协作者标注版场景推演（创建登录页）

```
Phase 0 触发
  [用户] "帮我创建登录页…5次锁定30分钟"
  [Selector] 预闸门命中 → decompose → 起 Orchestrator

Phase 1 Plan
  [Orchestrator] gather_context()（目录树+注册表+约束[+文档]）→ [Planner].plan(ctx)
  [Planner] LLM 一次 → [TaskDef t1,t2,t3]（只返回数据）
  [Orchestrator] build_graph 校验 → DAG；写 task_events；推 TaskPlanCard

Phase 2 派发
  [Orchestrator] tick: [Scheduler].compute_frontier→[t1,t2]; FSM→RUNNING; [Executor].dispatch(t1,t2)

Phase 3 执行 + 一个先完成
  [Executor] emit Heartbeat（刷 health，不改 FSM）
  T+25s [Executor] WorkerDone(t2)
  [Orchestrator] FSM t2→VERIFYING → [Verifier].verify(t2)
  [Verifier] pytest + reviewer → PASS
  [Orchestrator] FSM t2→COMPLETED; merge; tick（t3 未就绪）

Phase 3b 插话（不打断）
  [用户] "@Coordinator 加锁定没？"
  [Selector] 非 control → 分类=question → UserInterrupt
  [Orchestrator] 读 graph（t2 已含锁定）→ 机械回答（没调 Planner，t1 不受影响）

Phase 4 失败 → 重试
  T+50s [Executor] WorkerDone(t1) → [Verifier] 机械 PASS 但 reviewer 发现英文文案 → FAIL
  [Orchestrator] FSM t1→FAILED → handle_failure: retries<3 → FSM→RUNNING → [Executor].dispatch(t1)

Phase 5 重试成功 + 汇聚点回顾
  T+65s [Executor] WorkerDone(t1) → [Verifier] PASS → [Orchestrator] t1→COMPLETED; merge
  [Orchestrator] tick: frontier→[t3]; t3 是 fan-in → [Planner].review → on_track → [Executor].dispatch(t3)

Phase 6-7 测试 + 集成 + 收尾
  [Executor] WorkerDone(t3) → [Verifier] e2e PASS → t3→COMPLETED; merge
  [Orchestrator] AllDone → [Verifier].integration_gate(全量) PASS → [Planner].final_answer → 退出
```

每个时刻只有一个协作者在想/做，Orchestrator 串起来。无 god object，无越界改状态。

---

## 10. MVP 各协作者的薄形态

| 协作者 | MVP 形态 | 砍掉的 |
|--------|---------|--------|
| Planner | 一次 `chat_structured`，上下文预注入 | replan→重试问人、扩图、review |
| Scheduler | ✅ 已完整 | — |
| Executor | 派一个、**串行无 worktree**、盯活=硬超时 | worktree/并发/精细卡死 |
| Verifier | 只机械检查 | reviewer/集成闸门 |
| Orchestrator | 串行循环 + FSM + task_events + 退出码 | —（核心必做） |
| Selector | 加 decompose 预闸门 | 插话分类（只取消） |

同样 5 协作者，每个薄一层。复杂度在完整版才堆起来。

---

## 关联文档

- [[coordinator-dag-driven-design-v2]] v2.3 设计稿（确定性逻辑：DAG/FSM/调度/验证/事件循环细节）
- [[coordinator-test-plan]] 测试计划（§0 Ports 把 Planner/Worker/Clock/Harness 做成可注入接口）
- [[scenario-walkthrough-v2]] 旧场景推演（主语模糊，本文 §9 是协作者标注版）
