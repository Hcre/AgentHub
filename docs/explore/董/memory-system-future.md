# Agent 长期记忆系统 — 未来设计参考

> 日期：2026-05-29 | 状态：**仅作未来参考，不进当前 PRD**
> 来源：cc-haha 项目记忆系统分析（文件 D:\Edge_files\cc-haha_memory_system_analysis.md，未入仓）
> 触发：在群聊身份错乱方案讨论中识别到，cc-haha 的记忆系统设计值得未来引入 Agent 长期记忆时参考

## 一、为什么记下来不立刻做

- 当前 AgentHub 的核心问题是「单次会话内的 Agent 身份保持」，不是「跨会话的长期记忆缺失」
- 记忆系统是个独立子系统，与本次群聊修复正交，混在一起会拖慢两边
- cc-haha 的记忆系统是 1v1 场景的设计，N Agent 场景的适配仍需重新论证
- 当前没有任何业务/用户在抱怨「Agent 不记得我」

何时启动：当用户出现「希望 Agent 跨会话记住偏好」「希望团队成员共享某些上下文」类需求时，本文档作为设计起点。

## 二、cc-haha 记忆系统要点

### 2.1 分层结构

| 类型 | 路径 | 作用域 |
|------|------|--------|
| Auto-memory | `~/.claude/auto-memory/` | 用户级，全局 |
| Agent-memory | `~/.claude/agent-memory/<agent>/` | 单个 Agent，可分 user/project/local scope |
| Team-memory | `~/.claude/auto-memory/team/` | 团队共享，可 VCS |
| Session-memory | `~/.claude/session-memory/` | 单次会话临时 |

### 2.2 文件格式

```yaml
---
name: 用户角色信息
description: 用户是后端开发工程师，熟悉 Python/Go
type: user          # user | feedback | project | reference
tags: [开发者, 后端]
last_accessed: 2024-01-15
---

# 用户角色信息
（正文内容）
```

### 2.3 入口文件与截断

- `MEMORY.md` 作为索引入口，每条目 ≤150 字符
- 限制：200 行 / 25KB，超出截断并附警告
- 详细内容在主题文件中，索引只指向

### 2.4 智能检索（findRelevantMemories）

- 使用 Sonnet 模型而非关键词匹配
- 输入：用户当前 query
- 输出：最相关的 ≤5 个记忆文件
- 去重：过滤已展示给当前对话的记忆
- 工具感知：避免重复加载工具文档

### 2.5 注入方式

通过 `loadMemoryPrompt()` 将选中的记忆**注入到 System Prompt**：

```
System Prompt = [
  "# Claude Code",
  "You are a helpful coding assistant...",
  "[memory_section]",     ← 这里
  "[tools_section]",
  "[context_section]"
]
```

## 三、对 AgentHub 的潜在适配方向

### 3.1 复用要点

| cc-haha 设计 | AgentHub 适配 |
|-------------|--------------|
| frontmatter + type 分类 | 直接复用，type 可扩展为 `user/feedback/project/reference/team` |
| 入口文件 + 主题文件分离 | 直接复用 |
| AI 驱动的相关性检索 | 复用，但模型选择需考虑成本（每次查询调一次 LLM） |
| 多层 scope（user/project/local） | 复用，对应到 AgentHub 的 user/group/session 三级 |
| 团队共享记忆 | 适配为「群级共享记忆」—— 群所有 Agent 可读 |

### 3.2 需要重新设计的部分

| cc-haha 假设 | AgentHub 实际 | 需要的设计 |
|-------------|--------------|----------|
| 1v1 助手 | N Agent 群聊 | 每个 Agent 维护独立 agent-memory，群组 memory 共享 |
| CLI 进程本地文件系统 | 后端服务集群 | 记忆存储在 PG/Redis/对象存储，不是本地文件 |
| 用户主动管理 MEMORY.md | Agent 自主写入 + 用户编辑 | 需要写入审计、冲突处理 |
| Sonnet 检索每次调用 | 后端成本敏感 | 可分级：关键词 fast path + LLM slow path |

### 3.3 与 CLI 长驻方案的关系

cc-haha 长驻 CLI 模式下，记忆系统通过 `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` 环境变量让 CLI 自己读写记忆文件。

如果 AgentHub 也走长驻 CLI，可以：
- 选项 A：**CLI 内置记忆**（让 CLI 进程自管自读写文件，IM 层只配置路径） — 简单但难以做"群共享记忆"
- 选项 B：**IM 层管理 + 注入 System Prompt** — 与 cc-haha 一致，灵活但需要重启长驻进程才能更新（或定期重 spawn）
- 选项 C：**IM 层管理 + Tool API** — 提供 `get_memory` / `save_memory` 工具给 CLI 调用，运行时读写

选项 C 最契合 AgentHub 的多 Agent + 后端服务架构，但实现成本最高。

## 四、当前已有的相关基础

AgentHub 已有 L1/L2/L3 记忆抽象（`MemoryContext` 在 `protocol.py`），但当前只有 L1 working window 在用。其他三层（L2 summary / L3 specs / L4 RAG）已经预留接口：

```python
# protocol.py:MemoryContext
@dataclass
class MemoryContext:
    l1_working: list[dict]
    l2_summary: str | None = None
    l3_specs: str | None = None
    l4_rag: str | None = None
```

未来引入 cc-haha 风格的长期记忆，可以映射为：
- cc-haha agent-memory → AgentHub L2/L3
- cc-haha team-memory → AgentHub L3 group-level
- cc-haha findRelevantMemories → AgentHub L4 RAG 检索

## 五、待办（未来工单）

| # | 待办 |
|---|------|
| M1 | 用户调研：哪类记忆是真实需求？跨会话偏好？团队共享上下文？Agent 自我总结？ |
| M2 | 存储选型：PG（结构化）+ Redis（热缓存）+ 对象存储（大文本）的组合 |
| M3 | 检索策略分级：fast keyword path + slow LLM path |
| M4 | 写入审计与冲突处理（Agent 自主写入需要审批/限流） |
| M5 | 与长驻 CLI 进程的协作：选项 A/B/C 的具体取舍 |
| M6 | 权限模型：用户隐私、群共享边界、Agent 跨群泄漏防护 |

启动时机：当群聊身份方案（Phase 0/Phase 1）落地稳定，且至少有 1 个真实用户需求驱动后。
