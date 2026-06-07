# Agent 记忆系统 — V2 设计（借鉴 EverCore）

> 日期：2026-05-31 | 状态：**设计草案**
> 前置阅读：`memory-system-design-v1.md`（Phase A 基础）、`everos_evercore_memory_analysis.md`（EverCore 分析）
> 定位：在 V1 文件系统方案基础上，借鉴 EverCore 的记忆管理机制，增强记忆质量和生命周期管理

---

## 一、设计原则

**不改变底层架构**：继续使用文件系统 + SP 注入 + user message 通道，不引入外部记忆服务。

**借鉴 EverCore 的「机制」而非「基础设施」**：

| EverCore 做法 | 我们借鉴什么 | 不借鉴什么 |
|--------------|-------------|-----------|
| 7 种记忆类型分类 | 目录分类约定 | MongoDB/Milvus 基础设施 |
| AgentCase → AgentSkill 演进 | SP 指令引导 Agent 自行归纳 | LLM 自动聚类服务 |
| MemCell 边界检测 | 按对话主题分文件 | 独立边界检测服务 |
| 混合检索 (Vector+ES+BM25) | Agent 自主 grep/Read | 向量数据库 |
| ProfileMemory 用户画像 | preferences/ 分类 | 独立 Profile Extractor |
| Foresight 预测记忆 | context/ 下记录计划 | 时间维度索引服务 |
| 记忆分数 + 淘汰 | SP 指令 + 后台 cron | 实时 relevance scoring |

---

## 二、记忆分类体系

### 2.1 V1 现状

```
{agent_cwd}/memory/          # 扁平目录，Agent 自由写入，无结构约束
```

问题：
- Agent 写什么都往一个目录丢，容易变成垃圾场
- 无淘汰机制，token 只增不减
- 无法按类型检索相关记忆

### 2.2 V2 分类目录

```
{agent_cwd}/memory/
├── facts/              # 项目事实（不常变）
│   ├── arch-decisions.md      # "项目用 5 层洋葱架构"
│   ├── tech-stack.md          # "Python 3.12 + FastAPI + SQLAlchemy"
│   └── team-conventions.md   # "commit 用 conventional commits"
├── preferences/        # 用户/群组偏好（中频变更）
│   ├── user-dong.md           # "董偏好简洁回复，不要解释过程"
│   └── group-style.md        # "群里讨论用中文，代码用英文"
├── procedures/         # 操作流程（从经验中归纳）
│   ├── deploy-flow.md         # "部署三步：build → push → restart"
│   └── debug-api.md          # "API 500 排查：先看日志 → 查 DB → 查 Redis"
└── context/            # 长期上下文（高频衰减）
    ├── current-sprint.md      # "本周目标：完成记忆系统 Phase A"
    └── recent-decisions.md   # "昨天决定：SP 不含 ctx_hash"
```

### 2.3 与 EverCore 类型的映射

| EverCore 类型 | 我们的目录 | 说明 |
|--------------|-----------|------|
| AtomicFact | `facts/` | 不可变事实，手动更新 |
| ProfileMemory | `preferences/` | 显式偏好 + 隐式行为推断 |
| AgentCase → AgentSkill | `procedures/` | 案例归纳为流程 |
| Foresight | `context/` | 计划、预期、短期目标 |
| EpisodeMemory | 不保留 | 叙事性记忆价值低，占 token 多 |

---

## 三、记忆生命周期管理

### 3.1 写入规则（SP 指令约束）

Agent 写记忆时必须遵守：

```markdown
## 记忆写入规则

1. **归类**：写入前判断属于 facts/preferences/procedures/context 哪个目录
2. **格式**：每个文件首行标注元信息
   ```
   <!-- created: 2026-05-31 | updated: 2026-05-31 | hits: 0 -->
   ```
3. **粒度**：一个文件 = 一个独立知识点，不超过 30 行
4. **命名**：kebab-case，语义化，如 `deploy-flow.md` 而非 `note-1.md`
5. **去重**：写入前 grep 检查是否已有类似内容，有则更新而非新增
```

### 3.2 读取时机（按需检索）

借鉴 EverCore 的 `session-start` Hook 思路，但由 Agent 自主执行：

```markdown
## 记忆读取规则

每次收到新任务时：
1. 先 `ls memory/` 查看目录结构
2. 根据任务类型决定读哪些文件：
   - 代码任务 → Read facts/ + procedures/
   - 偏好相关 → Read preferences/
   - 规划任务 → Read context/
3. 只读标题相关的文件，不要全部加载
4. 读到过时信息时立即更新或删除
```

### 3.3 衰减与淘汰

#### 3.3.1 Agent 自律（Phase A，零代码改动）

SP 指令中加入淘汰规则：

```markdown
## 记忆淘汰规则

1. **context/ 目录**：超过 7 天未更新的文件，下次遇到时删除
2. **procedures/ 目录**：如果发现某流程已不适用，立即删除
3. **总量控制**：memory/ 下总文件数不超过 20 个
   - 超过时删除 context/ 中最旧的文件
   - 仍超过则合并 facts/ 中相关文件
4. **更新时刷新**：每次读取并使用某记忆时，更新 `hits` 计数和 `updated` 日期
```

#### 3.3.2 后台淘汰 cron（Phase B，需代码）

```python
class MemoryJanitor:
    """定时清理 Agent 记忆目录。"""

    async def sweep(self, agent_cwd: Path) -> int:
        """扫描 memory/，按规则淘汰过期文件。返回删除数。"""
        memory_dir = agent_cwd / "memory"
        deleted = 0

        for category in ["context", "procedures", "preferences", "facts"]:
            cat_dir = memory_dir / category
            if not cat_dir.exists():
                continue

            for f in cat_dir.iterdir():
                if not f.suffix == ".md":
                    continue
                meta = self._parse_meta(f)
                if self._should_evict(category, meta):
                    f.unlink()
                    deleted += 1

        return deleted

    def _should_evict(self, category: str, meta: dict) -> bool:
        """淘汰规则：context 7天、procedures 30天、preferences 90天、facts 永不自动淘汰。"""
        ttl_days = {"context": 7, "procedures": 30, "preferences": 90, "facts": None}
        ttl = ttl_days.get(category)
        if ttl is None:
            return False
        days_since_update = (datetime.now() - meta["updated"]).days
        return days_since_update > ttl
```

---

## 四、Case → Skill 演进机制

### 4.1 EverCore 的做法

```
多次执行同类任务 → 提取 AgentCase (quality_score)
→ 聚类相似 Case → 生成 AgentSkill (maturity_score)
→ 后续任务优先匹配 Skill
```

需要独立的 LLM 调用做聚类 + 归纳，部署复杂。

### 4.2 我们的简化实现

**靠 SP 指令引导 Agent 自行完成 Case → Skill 演进**，零基础设施成本：

```markdown
## 经验归纳规则

### 记录 Case
当你首次成功解决某类问题时，在 procedures/ 下创建文件，格式：

```md
<!-- created: YYYY-MM-DD | updated: YYYY-MM-DD | hits: 1 | type: case -->
# [问题简述]

## 场景
[什么时候会遇到这个问题]

## 步骤
1. ...
2. ...
3. ...

## 注意
[踩过的坑]
```

### 归纳 Skill
当你第 3 次执行同类任务时（通过 hits >= 3 判断），将 Case 升级为 Skill：
- 去掉具体细节，保留通用流程
- 将 type 改为 `skill`
- 提高抽象层次

### 淘汰低质量 Case
如果某 Case 记录的步骤在实际使用中失败了，降低信任：
- 第一次失败：在文件末尾加 `## 失败记录` 说明
- 第二次失败：删除该 Case
```

---

## 五、CLAUDE.md 索引增强

### 5.1 V1 现状

```markdown
# Agent 上下文

## 领域知识
- 技术栈（context/tech-stack.md）-- python, fastapi
- 代码规范（context/conventions.md）-- 后端专家
```

### 5.2 V2 增强（加入记忆索引）

```markdown
# Agent 上下文

## 领域知识
- 技术栈（context/tech-stack.md）-- python, fastapi
- 代码规范（context/conventions.md）-- 后端专家

## 记忆
- facts/（memory/facts/）-- 项目事实（架构、技术栈、约定）
- preferences/（memory/preferences/）-- 用户偏好（交互风格、审批习惯）
- procedures/（memory/procedures/）-- 操作流程（部署、排查、常见任务）
- context/（memory/context/）-- 短期上下文（本周目标、最近决策）

> 收到新任务时，按需 Read 相关记忆文件。不要一次性加载全部。
```

---

## 六、SP Memory 指令段（V2 完整版）

替换 V1 中 `SystemPromptBuilder._memory_instructions()` 的模板：

```markdown
# Memory

你拥有持久化记忆系统，位于 `{memory_path}`。

## 目录结构
```
memory/
├── facts/         # 不变的项目事实
├── preferences/   # 用户/群组偏好
├── procedures/    # 操作流程（经验归纳）
└── context/       # 短期上下文（7天衰减）
```

## 写入规则
- 归类到正确目录（facts/preferences/procedures/context）
- 文件首行：`<!-- created: YYYY-MM-DD | updated: YYYY-MM-DD | hits: 0 -->`
- 一个文件 = 一个知识点，不超过 30 行
- 写入前 grep 检查去重，有则更新
- kebab-case 命名，语义化

## 读取规则
- 新任务开始时，ls memory/ 并按需 Read 相关文件
- 使用记忆后更新 hits 和 updated 日期

## 淘汰规则
- context/：超过 7 天未更新 → 删除
- 总文件数不超过 20 → 超过则删最旧 context/
- 发现过时信息 → 立即删除或更新

## 经验归纳
- 首次解决某类问题 → 写 procedures/ 下的 Case（type: case）
- 第 3 次成功执行同类任务（hits >= 3）→ 升级为 Skill（type: skill）
- Case 步骤在实践中失败 2 次 → 删除
```

---

## 七、与 V1 的兼容性

| 维度 | V1 | V2 | 迁移成本 |
|------|-----|-----|---------|
| 目录结构 | `memory/`（扁平） | `memory/{facts,preferences,procedures,context}/` | Agent 首次 spawn 时自动创建子目录 |
| CLAUDE.md | 无记忆索引 | 加入记忆目录索引 | 修改 `_render_claude_md()` 模板 |
| SP Memory 指令 | 简单版 | 完整分类+淘汰+归纳规则 | 修改 `_memory_instructions()` 模板 |
| 后台淘汰 | 无 | `MemoryJanitor` cron | Phase B 新增 |
| 代码改动量 | — | ~80 行（模板文本 + mkdir） | 低风险 |

### 7.1 不变的部分

- 三层注入模型（Layer 1/2/3）不变
- SP 跨轮稳定、不含 ctx_hash — 不变
- 动态上下文走 user message 通道 — 不变
- `AgentFileManager`、`SystemPromptBuilder`、`ContextBuilder` 接口不变
- `GroupContext` 值对象不变

### 7.2 需要改的部分

1. `SystemPromptBuilder._memory_instructions()` → 替换为 V2 完整模板
2. `AgentFileManager.ensure_agent_cwd()` → 创建 `memory/{facts,preferences,procedures,context}/` 子目录
3. `AgentFileManager._render_claude_md()` → 加入记忆目录索引段
4. （Phase B）新增 `MemoryJanitor` 定时任务

---

## 八、多 CLI 兼容层（预留）

当前设计的 CLI 耦合点：

| 耦合点 | Claude Code 实现 | 其他 CLI 如何适配 |
|--------|-----------------|------------------|
| CLAUDE.md 自动注入 | 原生支持 | opencode → `.opencode/README.md`；pi → `.pi/config.md` |
| memory/ 路径约定 | `~/.claude/projects/{path}/memory/` | 统一改为 CWD 下 `memory/`（已如此） |
| Write 工具写文件 | 原生支持 | 所有 CLI 都有文件操作 |
| `--system-prompt` | 原生支持 | 大多数 CLI 支持类似参数 |

**结论**：唯一需要适配的是 CLAUDE.md 文件名。预留 `CLIProfile` 接口（V1 设计讨论中提出），Phase C 按需实现。

---

## 九、Phase 规划

| Phase | 内容 | 改动量 | 依赖 |
|-------|------|--------|------|
| **A（已完成）** | CWD + CLAUDE.md + context/ + SP Builder + user message 通道 | ~600 行 | 无 |
| **B1（本文档）** | 记忆分类目录 + SP 指令增强（分类/淘汰/归纳规则） | ~80 行（纯模板） | Phase A |
| **B2** | `MemoryJanitor` 后台淘汰 + hits 统计 | ~150 行 | Phase B1 |
| **C** | `CLIProfile` 多 CLI 适配层 | ~50 行 | 有第二个 CLI 接入时 |
| **D** | 群记忆共享（跨 Agent 记忆可见性） | 待设计 | Phase B2 |

---

## 十、效果预期

### 10.1 记忆质量

| 指标 | V1（无约束） | V2（分类+淘汰） | 预期提升 |
|------|-------------|----------------|---------|
| 记忆噪声率 | ~40%（无用文件多） | ~15% | -62% |
| Token 膨胀 | 线性增长，无上限 | 稳定在 20 文件以内 | 有界 |
| 相关记忆命中率 | 低（全量扫描） | 高（按类型定向 Read） | ~2x |
| 经验复用率 | 0（无归纳机制） | 逐步提升（Case→Skill） | 从无到有 |

### 10.2 与 EverCore 的取舍

| 我们放弃的 | 原因 |
|-----------|------|
| 向量检索 | Agent 可用 grep + 语义判断，文件数 < 20 时向量检索无优势 |
| 独立记忆服务 | 部署复杂度与收益不匹配（5 人团队） |
| 自动边界检测 | 由 Agent 自主判断写入时机，比外部检测更精准 |
| 多数据库存储 | 文件系统对小规模记忆（< 20 文件）是最优解 |
| 实时 relevance scoring | 20 文件内人工分类 + 目录名已足够定位 |

| 我们获得的 | 来源 |
|-----------|------|
| 记忆分类体系 | EverCore 7 类 → 我们 4 目录 |
| 生命周期管理（TTL） | EverCore relevance decay → 我们 SP 指令 + cron |
| Case→Skill 自我进化 | EverCore AgentSkill → 我们 SP 指令引导归纳 |
| 按需检索（不全量加载） | EverCore search API → 我们 Agent 自主 Read |
| 去重机制 | EverCore dedup → 我们 SP 指令要求 grep 检查 |

---

*文档结束。实现时只需修改 SP 模板文本 + ensure_agent_cwd 中加 4 个 mkdir。*
