# 记忆系统增强特性评估

> 日期：2026-05-30 | 基于 7 篇参考文档的全量探索，评估 9 项增强特性在 AgentHub 的适用性
> 参考：`memory-system-design-v1.md`、`cli-memory-boundary-experiments.md`、`ref-cc-haha-memory-arch.md`、`ref-cc-haha-memory-code.md`、`ref-cc-haha-context-flow.md`、`ref-memory-comparison.md`、`qa-record.md`、`../黎/群聊记忆系统高效组织方案.md`
> ⚠️ 本文档已根据 `cli-memory-boundary-experiments.md` 的实验结论修正（2026-05-30）

---

## 评估维度说明

每个特性按 4 个维度打分（⭐/❌），综合给出建议：

| 维度 | 含义 |
|------|------|
| **价值** | 对 AgentHub 群聊场景的实际效用 |
| **成本** | 实现复杂度 + 维护负担（⭐ = 低成本） |
| **时机** | 现在做还是以后做（现在 = 不依赖 Phase 1 长驻） |
| **风险** | 引入新问题/复杂度的可能性（⭐ = 低风险） |

---

## 一、Agent 筛选（Memory Filtering by Agent）

### 是什么

根据当前发言 Agent 的身份/角色/能力标签，从群共享记忆中筛选出与该 Agent 相关的部分，而非把所有群记忆无差别注入。

### 社区实践

| 来源 | 做法 |
|------|------|
| CrewAI | `MemorySlice`：Coordinator 为每个 Worker 裁剪"你需要的上下文"，不是全量 |
| PSMAS 论文 | 激活 Agent 注入完整上下文，闲置 Agent 只给一句话摘要 |
| cc-haha | 有 `@agent` 触发机制，但主要靠 Sonnet 语义选择，不做 per-agent 裁剪 |

### 评估

```
价值: ⭐⭐⭐⭐⭐  群聊核心需求。后端 Agent 不需要看前端 Agent 的 CSS 讨论
成本: ⭐⭐⭐⭐    在 ContextBuilder 中加一个 filter(agent_id, memories) 即可
时机: 现在       不依赖长驻 CLI，是 Coordinator 裁剪逻辑的一部分
风险: ⭐         几乎无风险，裁剪逻辑出错最多就是 Agent 信息不足
```

### 具体做法

```python
# ContextBuilder 中
def filter_memories_for_agent(
    memories: list[MemoryFile],
    agent: AgentDefinition,
    task: TaskContext | None = None,
) -> list[MemoryFile]:
    """只返回与该 Agent 相关的记忆。"""
    return [
        m for m in memories
        if (
            # 群决策：所有 Agent 都看
            m.type == "group-decision"
            # 同领域记忆：按能力标签匹配
            or any(tag in agent.capability_tags for tag in m.tags)
            # 该 Agent 的私有记忆
            or m.scope == f"agent:{agent.id}"
            # 当前任务相关
            or (task and any(kw in m.description for kw in task.keywords))
        )
    ]
```

### 结论

**必做，Phase A 就做。** 这是 Coordinator 裁剪的核心机制，是群聊记忆系统区别于 1v1 记忆的关键差异。

---

## 二、记忆扫描（Memory Scanning）

### 是什么

定期或按需扫描记忆文件目录，提取 frontmatter 元数据，构建可检索的索引。cc-haha 在每次对话前做这件事（`scanMemoryFiles`，只读前 30 行）。

### 社区实践

| 来源 | 机制 | 触发时机 |
|------|------|---------|
| cc-haha | `scanMemoryFiles()` 只读 frontmatter | 每次对话前 |
| AgentMemory | 12 个 Hooks 自动捕获 | 实时 |
| Claude-Mem | 生命周期钩子 | 会话开始/结束 |

### 评估

```
价值: ⭐⭐⭐⭐    索引是检索的前提。但 AgentHub 的文件数量远小于 cc-haha（每个 Agent 5-10 个文件）
成本: ⭐⭐⭐⭐⭐  极低。`os.listdir` + 读前 30 行，几十毫秒
时机: 现在       Phase A 渲染文件时同步更新索引，不需要后台扫描
风险: ⭐         几乎无风险
```

### 具体做法

AgentHub 不需要"扫描"——CLI 已经自动做了这件事。

**关键发现（来自 CLI 边界实验）**：CLI 在 `--system-prompt` 模式下仍会通过 `<system-reminder>` 自动注入 MEMORY.md 内容。这意味着：
- 每个 Agent 只要有独立 CWD，CLI 就会自动扫描该 CWD 对应的 `memory/MEMORY.md` 并注入
- AgentHub 只需要确保 Agent CWD 存在 + CLAUDE.md 已渲染，索引由 CLI 自动维护

```python
class AgentFileManager:
    def ensure_agent_cwd(self, agent_id: UUID) -> Path:
        """确保 Agent CWD 存在并渲染 CLAUDE.md。"""
        cwd = Path(f"/tmp/agenthub/agents/{agent_id}")
        cwd.mkdir(parents=True, exist_ok=True)
        # 渲染 CLAUDE.md — CLI 会通过 <system-reminder> 自动注入
        self._render_claude_md(agent_id, cwd / "CLAUDE.md")
        # memory/ 目录和 MEMORY.md 由 CLI 运行时自动创建和维护
        return cwd
```

### 结论

**成本比预估更低。** CLI 自动注入 MEMORY.md 内容（实验 2 已验证），AgentHub 不需要自己实现扫描和索引注入逻辑。只需确保 Agent CWD 隔离，CLI 自动完成余下工作。Phase C 如果引入 Agent 自主写入，memory/ 目录和 MEMORY.md 由 CLI 原生管理。

---

## 三、知识图谱（Knowledge Graph）

### 是什么

将记忆中的实体（Agent、任务、技术栈、决策）建模为图节点和边，支持关系查询（"上次做登录功能用了什么技术栈？"）。

### 社区实践

| 来源 | 做法 | 召回率 |
|------|------|--------|
| AgentMemory | BM25 + Vector + Graph 三路融合 | R@5 = 95.2% |
| Cognee | Session Memory + Knowledge Graph 双层查询 | — |
| Hindsight | 四维并行：语义 + 关键词 + 图谱 + 时间 | SOTA |
| Letta | 实验证明 grep + markdown（74%）> 专用图工具（68.5%） | — |

### 评估

```
价值: ⭐⭐⭐      对复杂多实体关系查询有价值，但 AgentHub 当前规模不需要
成本: ⭐          需要 Neo4j 或 PG 图扩展 + 实体提取 + 关系建模，工程量大
时机: Phase C    有真实需求后再做
风险: ⭐⭐        过度设计风险高。Letta 实验表明简单 grep 反超专用图工具
```

### 关键数据点

Letta 团队（Aug 2025）的核心发现：

> "What matters is whether the agent can effectively use the retrieval tool — exact retrieval mechanism (graphs vs. vectors) matters less than agent capabilities."

AgentMemory 的 95.2% R@5 是 BM25+Vector+Graph 三路融合的结果，不是纯图。纯图（Cognee）在简单查询上反而不如关键词匹配。

### AgentHub 的轻量替代

不需要建图数据库。用 **tags 关联 + 文件内 `[[wikilink]]`** 就能实现 80% 的图查询价值：

```markdown
---
name: 登录功能技术决策
tags: [auth, fastapi, jwt]
related: [[task-1]], [[auth.py]], [[JWT过期策略]]
---
```

Agent 通过 `grep "fastapi"` 和 `grep "\[\[auth.py\]\]"` 就能追踪关系链。

### 结论

**不做。** 用 tags + wikilink 替代，成本趋零。等群聊达到 50+ Agent、日均 100+ 决策记录的规模再考虑。

---

## 四、钩子系统（Hooks）

### 是什么

在关键生命周期节点（会话开始/结束、工具调用前/后、消息发送前/后、任务完成等）自动触发记忆捕获，无需用户/AI 手动标记。

### 社区实践

| 来源 | 机制 | 钩子数量 |
|------|------|---------|
| AgentMemory | MCP Server 拦截 CLI 内部事件 | 12 个 |
| Claude-Mem | 生命周期钩子自动捕获工具调用 | 4 个 |
| cc-haha | 无自动钩子，用户手动标记 | 0 |

AgentMemory 的 12 个钩子：
```
pre-tool-use, post-tool-use, post-tool-failure,
pre-compact, prompt-submit, session-start, session-end,
notification, stop, subagent-start, subagent-stop, task-completed
```

### 评估

```
价值: ⭐⭐⭐⭐⭐  全自动捕获是最理想的状态，用户/AI 不需要手动"记住"
成本: ⭐⭐        AgentHub 不能拦截 CLI 内部事件（和 AgentMemory 不同），
                 只能在 IM 层挂载 WS 消息拦截器 + 生命周期回调，覆盖 6-8 个钩子
时机: Phase B    依赖 Phase 1 长驻 CLI + Tool API
风险: ⭐⭐⭐      噪音风险高。自动捕获容易产生大量低质量记忆
```

### AgentHub 可行的钩子（IM 层）

AgentHub 不能拦截 CLI 内部事件（`pre-tool-use`、`pre-compact`、`subagent-*`），但在 IM 层可以挂载钩子。

**精简原则**：只做对记忆质量有确定价值的钩子，避免自动捕获产生低质量噪音。从 8 个候选项中筛选出 4 个高价值钩子：

| 钩子 | 触发点 | 捕获内容 | 为什么做 |
|------|--------|---------|---------|
| `on_task_completed` | TaskFSM → COMPLETED | 任务产物路径 + 结论 | 任务成果是最有价值的记忆来源，无噪音 |
| `on_task_failed` | TaskFSM → FAILED | 失败原因 + 上下文 | 失败经验比成功经验更值得记住 |
| `on_group_decision` | Coordinator 输出含决策标记 | 提取决策 → decisions.md | 群决策是群聊记忆的核心差异点 |
| `on_session_end` | WS 断开 / CLI 进程退出 | 生成会话摘要 | 为下次会话提供上下文延续 |

**被淘汰的 4 个**（噪音高于价值）：

| 钩子 | 淘汰原因 |
|------|---------|
| `on_session_start` | CLI 已自动注入 MEMORY.md，不需要额外的"加载历史记忆"动作 |
| `on_message_sent` | 每条消息都触发 → 噪音极高，关键词检测准确率不可控 |
| `on_agent_error` | CLI 进程退出已被 ProcessPool 监控，不需要独立钩子 |
| `on_idle_timeout` | 记忆编译 Phase C 才做（§六），触发器不应先于功能存在 |

### 结论

**做 4 个高价值钩子，不做 8 个。** 钩子越少越好——每个钩子都是一个噪音来源。Phase B 先做 4 个确定有价值的，验证噪音水平后再考虑扩展。钩子产出写入 Agent CWD 下的 memory/ 文件，由 CLI 自动索引。

---

## 五、渐进式披露（Progressive Disclosure）

### 是什么

将记忆按重要性/新鲜度分层，Agent 先看到最相关的摘要层，需要时再展开详情。避免一次性塞入全部记忆导致上下文膨胀。

### 社区实践

| 来源 | 机制 | 分层 |
|------|------|------|
| Claude-Mem | 三层渐进式披露 | L1: 最近 3-5 条（500 tokens）→ L2: 相关历史（2000 tokens）→ L3: 完整归档 |
| cc-haha | 入口截断机制 | MEMORY.md ≤200 行 → 主题文件按需加载 |
| Letta | Core/Recall/Archival 三层 | Core 永远在 context → Recall 工具搜索 → Archival 长期向量库 |

### 评估

```
价值: ⭐⭐⭐⭐⭐  Token 节省效果显著（Claude-Mem 官方数据 ~90%），直接降低 API 成本
成本: ⭐⭐⭐⭐   设计上就是 MEMORY.md 索引 + 主题文件分离，已经做了大半
时机: 现在       Phase A 文件渲染时就已经实现了"索引 + 详情"两层
风险: ⭐         几乎无风险，本质就是信息架构的分层设计
```

### AgentHub 的三层映射（修正版，对齐 CLI 边界实验结论）

根据 `cli-memory-boundary-experiments.md` 实验 2 的发现：`--system-prompt` 模式下 CLI 仍通过 `<system-reminder>` 自动注入 CLAUDE.md 和 MEMORY.md 内容。这意味着三层映射的实现路径与最初设想不同：

```
Layer 1: CLI 自动注入层（<system-reminder>，AgentHub 无需干预）
  ├── CLAUDE.md            Agent CWD 下的 CLAUDE.md → CLI 自动注入
  ├── MEMORY.md 索引       Agent memory/ 下的 MEMORY.md → CLI 自动注入
  ├── rules/*.md           规则文件 → CLI 自动注入
  └── gitStatus            Git 状态快照 → CLI 自动注入
  成本: 零（CLI 内置行为）

Layer 2: AgentHub 通过 --system-prompt 注入层（启动时固定，永不变）
  ├── Agent 身份/人格       从 PG agents 表渲染
  ├── # Memory 指令段      补回 CLI 丢失的记忆写入指令（见§九）
  └── 行为约束              Delivery Contract
  成本: AgentHub 构建 SP 的逻辑（一次性）
  注: 群聊上下文不再放 SP，改走 CLAUDE.md 动态段（见 memory-system-design-v1.md §五）
      → SP 永不变 → 永不杀进程 → 对话历史永不丢失

Layer 3: Agent 运行时主动查询层（grep / Read Tool）
  ├── memory/ 下的主题文件全文    按需展开
  ├── decisions.md 完整历史       Agent grep 查询
  └── 项目源码/文档                Agent 有完整文件系统访问权
  成本: 零（CLI 工具能力不受 --system-prompt 影响）
```

### 与原始设计的差异

| 原始假设 | 实验修正 |
|---------|---------|
| Layer 1 需要手动读 `.brain/soul.md` 注入 SP | Layer 1 由 CLI 自动完成，放 CLAUDE.md 到 Agent CWD 即可 |
| MEMORY.md 索引需要 AgentHub 代码读取并注入 | CLI 已自动注入 MEMORY.md 内容，AgentHub 不需要做 |
| 需要 `ContextBuilder` 类读文件构建 SP | SP 只需要包含 Agent 身份 + Memory 指令 + 群聊上下文 |

### 具体做法

```python
class SystemPromptBuilder:
    def build_agent_sp(self, agent: AgentDefinition, group_ctx: GroupContext | None) -> str:
        """构建 --system-prompt 内容。

        注意: CLAUDE.md 和 MEMORY.md 由 CLI 通过 <system-reminder> 自动注入，
        这里只需要构建 CLI 替换掉的部分。
        """
        parts = [
            # Agent 身份（替代 CLI 默认的 "You are Claude Code..."）
            agent.system_prompt,
            # 补回 # Memory 指令段（CLI 用 --system-prompt 后丢失）
            self._memory_instructions(agent.cwd),
            # 行为约束
            agent.delivery_contract,
        ]
        if group_ctx:
            parts.append(self._group_context(group_ctx))
        return "\n\n".join(p for p in parts if p)
```

### 结论

**必做，且实现成本比原估更低。** Layer 1 由 CLI 免费提供，AgentHub 只需要关注 Layer 2（SP 构建）。Layer 3 由 CLI 工具能力天然支持。核心工作量从"读文件构建上下文"缩减为"构建 SP 模板"。

---

## 六、记忆编译（Memory Compilation）

### 是什么

当记忆文件过多（cc-haha 阈值：10 个）或会话空闲时，将分散的记忆按主题聚合成结构化摘要，减少文件数量、提升检索效率。

### 社区实践

| 来源 | 触发条件 | 编译方式 |
|------|---------|---------|
| cc-haha | 文件 >10 + 会话空闲 5 分钟 | AI 按主题分组 → 摘要 |
| AgentMemory | Session End Hook | 自动生成 session 摘要 |
| Claude-Mem | 会话结束 | 生成观察摘要 |

### 评估

```
价值: ⭐⭐⭐      文件多了有用，但 AgentHub 初始每个 Agent 就 5-6 个文件，短期内不会触发
成本: ⭐⭐⭐      需要 AI 调用做摘要，与记忆检索的成本类似
时机: Phase C    文件数 <20 时不需要，手动整理更可控
风险: ⭐⭐        AI 编译可能丢失细节，需要保留原始文件作为 fallback
```

### 结论

**不做，等文件数自然增长到 20+ 再考虑。** 当前每个 Agent 的文件数（soul/base/act/dream + 3-5 个记忆主题）远低于编译阈值。

---

## 七、防重复注入（Deduplication）

### 是什么

确保同一条记忆不会在连续多轮对话中重复注入，避免浪费 token 和干扰 Agent 注意力。

### 社区实践

| 来源 | 机制 |
|------|------|
| cc-haha | `alreadySurfaced: Set<string>` 记录已选路径，过滤 + `FileStateCache` 过滤用户已读 |
| AgentMemory | Session 级别去重，同 session 不重复 |
| Claude-Mem | 最近 3-5 条摘要不去重，L2/L3 做去重 |

### 评估

```
价值: ⭐⭐⭐⭐⭐  群聊多轮对话中，同一份 decisions.md 不能每轮都重复注入
成本: ⭐⭐⭐⭐⭐  一个 Set 的事，极低
时机: 现在       Phase A 就能做
风险: ⭐         去重过度可能让 Agent 丢失上下文，加个过期时间即可
```

### 具体做法

```python
class MemoryInjector:
    def __init__(self):
        self._surfaced: dict[str, set[str]] = {}  # session_id → {file_paths}
        self._surfaced_at: dict[str, float] = {}   # file_path → timestamp

    def should_inject(self, session_id: str, file_path: str, ttl: int = 300) -> bool:
        """TTL 内不重复注入同一文件。"""
        key = f"{session_id}:{file_path}"
        now = time.time()
        if key in self._surfaced_at:
            if now - self._surfaced_at[key] < ttl:
                return False
        self._surfaced_at[key] = now
        return True
```

### 结论

**必做，Phase A 就做。** 实现成本趋零，但显著改善体验。

---

## 八、混合检索（Hybrid Search）

### 是什么

组合多种检索策略（关键词 BM25 + 语义向量 + 图关系 + 时间衰减），按权重融合排序，比单一策略的召回率高。

### 社区实践

| 来源 | 策略 | 召回率 |
|------|------|--------|
| AgentMemory | BM25 + Vector + Graph 三路 + RRF 融合 | R@5 = 95.2% |
| Hindsight | 语义 + 关键词 + 图谱 + 时间四维并行 | SOTA |
| CrewAI | 语义相似度 ×0.5 + 时间衰减 ×0.3 + 重要性 ×0.2 | — |
| cc-haha | 仅 Sonnet 语义选择 | 依赖 AI |

### 评估

```
价值: ⭐⭐⭐      对大量记忆（100+）效果显著，AgentHub 初期每个 Agent <20 条记忆
成本: ⭐⭐        BM25 简单（SQLite FTS5），但 Vector 需要 embedding 基础设施
时机: Phase C    记忆量 <50 时，grep 关键词匹配足够
风险: ⭐⭐        引入 embedding 增加依赖，与"不需要向量库"的设计原则冲突
```

### AgentHub 的分级检索策略

```
Phase A（当前）: grep 关键词匹配
  └─ 从 MEMORY.md 索引 + 主题文件 frontmatter 中匹配

Phase B（有 Tool API 后）: 关键词 + 时间衰减
  └─ CrewAI 公式简化版：keywords_match × 0.5 + recency × 0.3 + is_pinned × 0.2

Phase C（记忆 >100 条后）: + LLM 语义选择
  └─ 参考 cc-haha：Sonnet/4o-mini 选择 ≤5 条最相关
  └─ 成本：~500ms + ~$0.001/次
```

### 结论

**不做混合检索，做分级演进。** Phase A grep，Phase B 加时间衰减公式，Phase C 加 LLM 语义选择。每个阶段只加一种策略，验证效果后再加下一种。

---

## 九、记忆写入指令（Memory Write Instructions）

### 是什么

在 `--system-prompt` 中补回 CLI 丢失的 `# Memory` 指令段，让 Agent 具备主动写记忆的能力。这不是一个"功能"，而是使用 `--system-prompt` 方案的**必要补丁**。

### 为什么需要

CLI 边界实验（实验 2、实验 5）明确证实：
- `--system-prompt` 替换了 CLI 的 `# Memory` 指令段
- 指令消失后，Agent **不会主动写记忆**（没有指令驱动）
- 但 CLI 的 Write/Read 工具仍在，Agent **有能力**写记忆，只是**没有动机**

因此 AgentHub 必须在 SP 中补回记忆写入指令，告诉 Agent：
1. 记忆路径在哪里
2. 文件格式是什么（frontmatter）
3. 什么时候应该写记忆
4. MEMORY.md 索引如何维护

### 评估

```
价值: ⭐⭐⭐⭐⭐  没有这个指令，Agent 就是一个无记忆体。方案 A 的前置依赖
成本: ⭐⭐⭐⭐    几行模板文本，参考 CLI 原生 # Memory 段即可
时机: 现在       Phase A 必做，与 SP 构建同步实现
风险: ⭐⭐        指令过长占 token，指令过短 Agent 写出的记忆格式不对
```

### 具体做法

SP 中嵌入的 Memory 指令段（精简版，~300 tokens）：

> **注意路径**：`cli_memory_path` = `~/.claude/projects/-{cwd 中 / 替换为 -}/memory/`，
> 不是 Agent CWD 下的 `memory/`。两者不同，CLI 只从前者读取并自动注入。

```markdown
# Memory
You have a persistent file-based memory at `{cli_memory_path}`.
Write to it directly with the Write tool.

Each memory file uses this frontmatter format:
---
name: {{name}}
description: {{one-line description}}
type: {{knowledge | feedback | reflection}}
---
{{content}}

Maintain MEMORY.md as a one-line-per-entry index. Keep entries under 150 chars.

When to save:
- Task conclusions and key decisions
- Learnings from failures
- User preferences and corrections
- Group decisions that affect future work

Do NOT save: ephemeral task details, code patterns visible in source, git history.
```

### 与 CLI 原生指令的差异

| CLI 原生 `# Memory` 段 | AgentHub 精简版 |
|------------------------|----------------|
| ~2000 tokens | ~300 tokens |
| 6 种 type（user/feedback/project/reference/...） | 3 种 type（knowledge/feedback/reflection） |
| 复杂的保存规则和排除规则 | 4 条简明规则 |
| 个人用户场景优化 | 群聊 Agent 场景优化 |

精简理由：Agent 不需要区分"user memory"和"project memory"——Agent 本身就是项目的一部分。3 种 type 足够覆盖群聊场景。

### 结论

**Phase A 必做，是方案 A 的前置依赖。** 没有记忆写入指令的 Agent 就是一个无记忆体。实现成本极低（模板文本），但效果决定了整个记忆系统能否运转。

---

## 总结：优先级矩阵

| # | 特性 | 价值 | 成本 | 时机 | 风险 | 建议 |
|---|------|:---:|:---:|:---:|:---:|------|
| 1 | **记忆写入指令** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 现在 | ⭐⭐ | **Phase A 必做，方案 A 的前置依赖** |
| 2 | **Agent 筛选** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 现在 | ⭐ | **Phase A 必做** |
| 3 | **渐进式披露** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 现在 | ⭐ | **Phase A，Layer 1 由 CLI 免费提供** |
| 4 | **防重复注入** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 现在 | ⭐ | **Phase A 必做** |
| 5 | **记忆扫描** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 现在 | ⭐ | **CLI 自动完成，不需独立系统** |
| 6 | **钩子系统** | ⭐⭐⭐⭐ | ⭐⭐⭐ | Phase B | ⭐⭐ | **Phase B 做 4 个高价值钩子** |
| 7 | **混合检索** | ⭐⭐⭐ | ⭐⭐ | Phase C | ⭐⭐ | **分级演进，不做一步到位** |
| 8 | **记忆编译** | ⭐⭐⭐ | ⭐⭐⭐ | Phase C | ⭐⭐ | **不做，<20 文件不需要** |
| 9 | **知识图谱** | ⭐⭐⭐ | ⭐ | Phase C+ | ⭐⭐ | **不做，tags+wikilink 替代** |

### 实施顺序

```
Phase A（立即可做，不依赖长驻 CLI）:
  ✅ 记忆写入指令      → SP 模板中补回 # Memory 段（~300 tokens）
  ✅ Agent CWD 隔离    → AgentFileManager.ensure_agent_cwd() + CLAUDE.md 渲染
  ✅ Agent 筛选        → Coordinator 裁剪群记忆（filter by agent tags）
  ✅ 渐进式披露        → Layer 1 CLI 自动注入 / Layer 2 SP 构建 / Layer 3 Agent 自主查询
  ✅ 防重复注入        → MemoryInjector.should_inject() + TTL
  ✅ 记忆扫描          → CLI 自动注入 MEMORY.md（零成本）

Phase B（依赖 Phase 1 长驻 CLI + Tool API）:
  🟡 钩子系统（4 个）  → on_task_completed / on_task_failed / on_group_decision / on_session_end
  🟡 分级检索 Step 2   → 时间衰减公式

Phase C（有真实需求驱动）:
  🔵 LLM 语义选择      → 替代纯 grep，对标 cc-haha findRelevantMemories
  🔵 记忆编译          → 文件数 >20 后启用

不做:
  ❌ 知识图谱          → tags + wikilink 替代
  ❌ 向量检索          → 与"不引入 pgvector"的设计原则冲突
  ❌ CLI 内部 Hooks    → AgentHub 拦截不到 CLI 内部事件
  ❌ on_message_sent   → 噪音太高，关键词检测准确率不可控
```

---

> **关键原则**：记忆系统的演进不是加功能，而是**控制 Agent 看到的信息量和精确度**。
>
> CLI 边界实验的核心收益：Layer 1（CLAUDE.md + MEMORY.md 注入）和 Layer 3（Read/Write/Grep 工具能力）由 CLI 免费提供。AgentHub 只需要关注 Layer 2 — 用 `--system-prompt` 注入 Agent 身份 + 记忆写入指令 + 群聊上下文。这将实现成本从"构建完整记忆系统"缩减为"构建 SP 模板 + Agent CWD 管理"。
