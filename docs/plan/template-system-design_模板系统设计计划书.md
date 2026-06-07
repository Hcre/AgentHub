# AgentHub 模板系统设计计划书（终版 v3.0）

> **版本**: v3.0（终版）
> **日期**: 2026-06-07
> **状态**: 已确认，进入实施
> **作者**: AgentHub Team

---

## 一、背景与目标

### 1.1 现状问题

1. **8 个模板硬编码在前端**。`CreateAgentModal.tsx:21-62` 中 `TEMPLATES` 数组是 TypeScript 常量。
2. **模板不可扩展**。用户无法创建、编辑、克隆、导出自己的模板。
3. **Skill 创建入口缺失**。`SkillMarketplacePage.tsx` 第 278 行「创建 Skill」按钮引用了未定义的 state。
4. **模板与 Agent 之间无溯源链**。Agent 创建后忘记了自己来自哪个模板。
5. **术语冲突**。MCP 模块已有 `GET /api/mcp/market/templates`。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **wshobson/agents 原生格式** | 直接采用其 agent markdown 格式作为模板格式 |
| **GitHub 唯一源** | MVP 仅使用 wshobson/agents 一个仓库作为模板源 |
| **文件系统 + DB 索引** | Git clone 模板源到本地文件系统，DB 存索引元数据 |
| **快照模式** | Agent 创建时从模板复制字段，模板更新不联动 |
| **独立目录** | `.agenthub/templates/` 与 `.agenthub/skills/` 完全隔离 |
| **中文翻译** | 手动翻译高频模板的中文展示名和描述 |

### 1.3 核心目标

| 目标 | 验收标准 |
|------|---------|
| **模板可发现** | 从 wshobson/agents clone → 解析 agent .md 文件 → DB 索引 → UI 可浏览/搜索/选择 |
| **模板驱动创建** | CreateAgentModal Step 1 动态加载模板列表，硬编码 TEMPLATES 退役 |
| **Skill 创建可用** | 手工表单 + AI 字段生成 + CLI AI 队友引导式创建 |
| **溯源链** | Agent 记录 `created_from_template_id`（快照，不联动更新）|
| **术语不冲突** | Agent 模板对外称「Agent 蓝图 / Blueprint」 |

---

## 二、模板文件格式

### 2.1 wshobson/agents 原生格式

直接采用，不做包装：

```yaml
---
name: python-pro
description: Master Python 3.12+ development with modern tools...
model: opus                     # opus | sonnet | haiku | inherit
tools:                          # 可选：允许的工具
  - read
  - write
  - bash
color: "#3776AB"                # 可选：显示颜色
---

## Purpose
一段话总结 agent 做什么

## Capabilities
- 能力列表

## Behavioral Traits
- 行为特质

## Knowledge Base
- 领域知识

## Response Approach
1. 响应步骤

## Example Interactions
- 示例对话
```

### 2.2 AgentHub 扩展层

原始 .md 文件来自 GitHub clone，**只读不改**。AgentHub 在 DB 索引中补充展示层字段：

| 扩展字段 | 来源 | 用途 |
|----------|------|------|
| `display_name_zh` | 手动翻译 | 模板卡片中文名 |
| `description_zh` | 手动翻译 | 模板卡片中文描述 |
| `recommended_skills` | AgentHub 维护 | 推荐该模板绑定的 Skill slug |
| `compatible_agent_systems` | 自动推导 | 该模板兼容的 CLI 运行时列表 |
| `compatible_providers` | 自动推导 | 该模板兼容的 LLM 提供商列表 |

### 2.3 model tier 映射

wshobson/agents 的 `model: opus/sonnet/haiku/inherit` 映射到各 provider 的具体模型：

| Tier | Anthropic | DeepSeek | OpenAI | Gemini | MiniMax |
|------|-----------|----------|--------|--------|---------|
| **opus** | claude-opus-4-8 | deepseek-v4-pro | gpt-5 | gemini-2.5-pro | — |
| **sonnet** | claude-sonnet-4-6 | deepseek-chat | gpt-4o | gemini-2.5-flash | minimax-text-01 |
| **haiku** | claude-haiku-4-5 | deepseek-chat | gpt-4o-mini | gemini-2.5-flash | — |
| **inherit** | 用户默认 | 用户默认 | 用户默认 | 用户默认 | 用户默认 |

映射逻辑在前端 `cliProviderMatrix.ts` 中扩展，后端模板详情也返回推荐的模型名。

### 2.4 CLI 兼容性

| AgentSystem | system_prompt | model tier | 备注 |
|-------------|:---:|:---:|------|
| **claude_code** | ✅ | ✅ 原生 | wshobson/agents 的主 target |
| **codex** | ✅ | ⚠️ 映射 | Codex 用 GPT 系列 |
| **opencode** | ✅ | ⚠️ 映射 | OpenCode 多 provider |
| **gemini** | ✅ | ⚠️ 映射 | Gemini 模型名不同 |
| **cursor_agent** | ✅ | ⚠️ 映射 | Cursor 用 GPT 系列 |
| **pi_agent** | ✅ | ⚠️ 映射 | 通过 `--system-prompt` CLI 参数直接传入 |
| **anthropic_api** | ✅ | ✅ 可用 | API 模式下 system prompt 即 system message |
| **openai_api** | ✅ | ⚠️ 映射 | 同上 |
| **mock** | ✅ | N/A | 无论如何都工作 |

**关键结论**：system_prompt body 是纯文本，**所有 9 个 AgentSystem 全部兼容**。`model` 字段只是推荐值，AgentHub 在创建 Agent 时做 provider → model 翻译。pi_agent 通过 `--system-prompt` CLI 参数接收，**无需额外适配器**。

### 2.5 文件布局

```
.agenthub/
  templates/                         # ★ 新增：模板独立目录
    sources.json                     # 模板源清单
    wshobson-agents/                 # git clone --depth 1 自 wshobson/agents
      plugins/
        python-development/agents/
          python-pro.md
          django-pro.md
          fastapi-pro.md
        frontend/agents/
          ...
        ...
    my-templates/                    # 用户自建模板（gitignored）
      my-custom-agent.md
```

`sources.json`：
```json
{
  "sources": [
    {
      "id": "wshobson-agents",
      "url": "https://github.com/wshobson/agents.git",
      "branch": "main",
      "enabled": true,
      "description_zh": "wshobson/agents 官方仓库，192 个精选 Agent 模板",
      "last_synced": null
    }
  ]
}
```

---

## 三、涉及改动的界面

### 3.1 创建 Agent Step 1（模板选择）

**改造**：硬编码 8 模板 → 从 API 动态加载 wshobson/agents 模板 + 本地模板

```
┌──────────────────────────────────────────────┐
│  创建你的新 AI 队友                  Step 1/3 │
│                                              │
│  [🔍 搜索模板…]                               │
│                                              │
│  ┌─ 模板列表 ────────────────────────────┐   │
│  │ ┌──────────┐ ┌──────────┐ ┌────────┐  │   │
│  │ │🐍 Python │ │🏗️ 技术   │ │📋 代码  │  │   │
│  │ │  Pro     │ │  负责人   │ │ 评审    │  │   │
│  │ │ opus     │ │ inherit  │ │ sonnet  │  │   │
│  │ │ wshobson │ │ 我的模板  │ │ wshobson│  │   │
│  │ └──────────┘ └──────────┘ └────────┘  │   │
│  │                                        │   │
│  │ ┌──────────────────────────────────┐   │   │
│  │ │ ＋ 自定义（从零创建）              │   │   │
│  │ └──────────────────────────────────┘   │   │
│  └────────────────────────────────────────┘   │
│                                              │
│  点击模板 → 右侧滑出预览面板：                  │
│    - 完整 system_prompt 内容                  │
│    - 兼容的 CLI 列表                          │
│    - 来源：wshobson/agents                    │
│    - [使用此模板] 按钮                        │
│                                              │
│  [取消]                          [下一步]     │
└──────────────────────────────────────────────┘
```

**关键交互**：
- 模板卡片：name（英文）+ 中文展示名（翻译后）、model tier 彩色徽章、来源标签
- 点击卡片 → 预览面板（右侧滑出）
-「自定义」保留，放在网格末尾
- 加载中：6 张骨架卡片
- 模板源未同步：顶部横幅「正在从 GitHub 获取模板…」

### 3.2 Skill 创建向导（含 AI 队友引导）

**三个入口**：

| 入口 | 位置 | 说明 |
|------|------|------|
| **A（主入口）** | Skill 市场「已安装」Tab →「+ 创建 Skill」按钮 | 弹出双路径选择面板 |
| **B（模板入口）** | 创建 Agent Step 1 → 选择「Skill 设计师」模板 → 走完整创建流程 | 创建 Skill 设计师 Agent → 私聊对话引导 |
| **C（自然语言）** | 任何私聊中说「帮我创建一个 skill」 | 已有 Agent 检测到 `capability_tags` 含 `skill-creation` 则切入引导模式 |

#### 入口 A 流程

```
[+ 创建 Skill] 按钮
    │
    ├── 「快速创建」Tab → 手工表单
    │       name / description / triggers / instructions / examples
    │       → POST /api/skills/library/create
    │
    ├── 「AI 生成」Tab → 自然语言描述
    │       → POST /api/skills/library/generate（已有后端）
    │       → LLM 返回预填字段 → 可编辑 → 确认保存
    │
    └── 「AI 助手引导」→ 创建 Skill 设计师 Agent
            → 选中「Skill 设计师」模板
            → 跳转创建向导 Step 2/3
            → 创建完成后自动打开私聊
```

#### 入口 B 流程（CLI AI 队友引导）

```
创建向导 Step 1 → 选择「Skill 设计师」模板
    ↓
Step 2 → 选择 CLI 运行时 + Provider → 创建 Agent
    ↓
Agent 上线 → 自动打开私聊
    ↓
Skill 设计师 Agent 发首条消息：「你想创建什么类型的 skill？」
    ↓
多轮对话（4 个 Phase）：

Phase 1 — 探索：
  Agent: 这个 skill 要解决什么问题？一句话描述。
  User:  自动生成小红书爆款标题
  Agent: 用户在什么情况下会用到？给我 3-5 个触发词。
  User:  「写标题」「帮我起个标题」「这个文案配什么标题」
  Agent: 执行步骤、约束条件、输出格式有要求吗？
  ...

Phase 2 — 草稿生成：
  Agent 输出完整 SKILL.md（markdown 代码块），询问是否满足需求

Phase 3 — 修改循环（最多 3 轮）：
  用户反馈 → Agent 修改 → 重新展示

Phase 4 — 最终确认：
  Agent: 「确认无误后我会保存 SKILL.md。确认保存？」
  → Agent 通过 Write tool 写入 {SKILLS_DIR}/{slug}/SKILL.md

保存检测：
  前端 5s 内轮询 GET /api/skills/library 检测新 skill → toast + 刷新列表
  降级：前端从对话消息解析 SKILL.md → POST /api/skills/library/create
```

#### 对话中断恢复

- 消息持久化在 sessions → messages 表
- 重新打开 AgentHub → 点击 Skill 设计师 Agent 私聊 → 恢复会话
- Agent 每轮检查对话历史，跳过已答问题
- `localStorage.skill_creation_draft: {conversationId}` 快速恢复（24h TTL）

#### CLI 不可用降级

| CLI 状态 | 可用路径 |
|---------|---------|
| Claude Code CLI 正常 | 引导 + 手工 + AI 生成 |
| Pi Agent CLI 正常 | 引导 + 手工 + AI 生成 |
| 仅 Mock | 仅手工 + AI 生成（横幅提示安装 CLI 解锁引导） |

### 3.3 模板管理页

在 Skill 市场页增加第三个 Tab「模板」。

```
[市场] [已安装] [模板]  ← 三个 Tab

模板 Tab：
  ├── 模板源状态卡片：
  │     ┌─ wshobson/agents ────────────────┐
  │     │ ✅ 已同步 · 192 个模板             │
  │     │ 上次同步：2026-06-07 14:30        │
  │     │ [浏览模板] [重新同步]              │
  │     └──────────────────────────────────┘
  │     ┌─ 我的模板 ────────────────────────┐
  │     │ 📁 本地 · 3 个模板                 │
  │     │ [浏览模板] [+ 新建] [导入 .md]     │
  │     └──────────────────────────────────┘
  │
  ├── 点击「浏览模板」→ 模板网格（同 Step 1 布局）
  │     每张卡片额外：[查看详情] [克隆为本地] [导出 .md]
  │     远程模板：只读。本地模板：可编辑/删除
  │
  └── 空状态：「尚未同步模板源」+ 一键同步按钮
```

### 3.4 组件变更清单

| 组件 | 操作 | 说明 |
|------|------|------|
| `CreateAgentModal.tsx` | 重构 | Step 1 改为动态模板选择；移除硬编码 TEMPLATES（保留 fallback） |
| `TemplateGrid.tsx` | 新建 | 模板卡片网格 + 搜索/筛选 |
| `TemplateCard.tsx` | 新建 | 模板摘要卡片（name, 中文名, model tier badge, 来源） |
| `TemplatePreviewPanel.tsx` | 新建 | 滑动预览面板 |
| `SkillMarketplacePage.tsx` | 修改 | 加第 3 Tab「模板」；修复 createSkillOpen state |
| `CreateSkillDialog.tsx` | 新建 | 三路径选择：快速创建 / AI 生成 / AI 助手引导 |
| `SkillCreationWizard.tsx` | 新建 | AI 助手引导路径的入口管理 |
| `MessageBubble.tsx` | 修改 | 检测 SKILL.md 代码块 → 渲染预览面板 + 保存按钮 |
| `templateStore.ts` | 新建 | Zustand store：模板列表 + 模板源管理 |
| `uiStore.ts` | 修改 | Section 联合类型增加 `template-management` |
| `agentStore.ts` | 修改 | CreateAgentInput 增加 `capabilityTags` |

---

## 四、后端设计

### 4.1 存储方案

```
wshobson/agents (GitHub)
    │ git clone --depth 1
    ▼
.agenthub/templates/wshobson-agents/
    │ 扫描 plugins/*/agents/*.md
    ▼
解析器（YAML frontmatter + 章节提取 + model tier 识别）
    │
    ├──→ templates 表（DB）：元数据索引 + 扩展字段
    │      id, source_path, name, description, model_tier, tools, color
    │      display_name_zh, description_zh, recommended_skills
    │      compatible_agent_systems, compatible_providers
    │
    └──→ 模板详情 API：从源文件实时读取完整 system_prompt body
```

### 4.2 API 端点

所有端点放在 `/api/templates` 下。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/templates` | 列表。`?q=&model_tier=&page=&page_size=` |
| `GET` | `/api/templates/{id}` | 详情（含完整 system_prompt body） |
| `POST` | `/api/templates` | 创建本地模板（→ `my-templates/` + DB） |
| `PATCH` | `/api/templates/{id}` | 更新本地模板（仅 source='local'） |
| `DELETE` | `/api/templates/{id}` | 删除本地模板 |
| `POST` | `/api/templates/sync` | 同步模板源（git pull → 重新扫描 → 更新 DB） |
| `GET` | `/api/templates/source` | 获取模板源状态 |
| `GET` | `/api/templates/{id}/export` | 导出为 .md 文件下载 |

### 4.3 数据模型

```sql
-- 模板索引表
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(16) NOT NULL DEFAULT 'wshobson',  -- 'wshobson' | 'local'
    source_path VARCHAR(1024) NOT NULL,               -- 相对 templates/ 的文件路径
    name VARCHAR(128) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    model_tier VARCHAR(16) NOT NULL DEFAULT 'inherit',
    tools JSONB NOT NULL DEFAULT '[]',
    color VARCHAR(7),

    -- AgentHub 扩展
    display_name_zh VARCHAR(128),
    description_zh TEXT,
    recommended_skills JSONB NOT NULL DEFAULT '[]',
    compatible_agent_systems JSONB NOT NULL DEFAULT '[]',
    compatible_providers JSONB NOT NULL DEFAULT '[]',

    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 模板源状态表
CREATE TABLE template_source (
    id VARCHAR(128) PRIMARY KEY,
    url VARCHAR(1024) NOT NULL,
    branch VARCHAR(128) NOT NULL DEFAULT 'main',
    description_zh TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    template_count INTEGER NOT NULL DEFAULT 0,
    last_synced TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- agents 表新增
ALTER TABLE agents ADD COLUMN created_from_template_id UUID;
```

### 4.4 新增/修改文件清单

| 层级 | 文件 | 操作 |
|------|------|------|
| L1 Infra | `infrastructure/template/git_manager.py` | 新建：git clone/pull/validate |
| L1 Infra | `infrastructure/template/parser.py` | 新建：YAML frontmatter 解析 + wshobson/agents 格式校验 |
| L1 Infra | `infrastructure/repositories/template_repository.py` | 新建：PostgresTemplateRepository |
| L2 Domain | `domain/entities/template.py` | 新建：Template + TemplateSource 数据类 |
| L2 Domain | `domain/repositories/template_repository.py` | 新建：TemplateRepository ABC |
| L3 App | `application/services/template_service.py` | 新建：CRUD + 同步 + 导出 |
| L4 Schema | `schemas/template.py` | 新建：Pydantic v2 请求/响应 |
| L4 API | `api/routers/templates.py` | 新建：FastAPI router（8 个端点） |
| L4 API | `api/deps.py` | 修改：新增 template 依赖注入 |
| DB | `infrastructure/db/models.py` | 修改：+ TemplateModel, TemplateSourceModel, AgentModel.created_from_template_id |
| Migration | Alembic | 新建：创建表 + ALTER agents |
| Seed | 数据迁移脚本 | 新建：40 个常用模板的中文翻译数据 |

### 4.5 同步流程

```
系统启动 / 用户手动触发 POST /api/templates/sync
  ├── 1. 检查 sources.json → 取 wshobson-agents 源
  ├── 2. 目录存在？→ git pull（增量更新）
  │         不存在？→ git clone --depth 1
  ├── 3. 扫描：walk plugins/*/agents/*.md
  ├── 4. 逐个解析 YAML frontmatter：
  │     - 提取 name, description, model, tools, color
  │     - 验证必填字段（name, description）
  │     - 跳过解析失败的文件（记录日志）
  ├── 5. 与 DB 比对（新增/修改/删除）
  ├── 6. 事务写入 DB（INSERT/UPDATE/DELETE）
  ├── 7. 对新增模板：调用 LLM 翻译中文名和描述
  └── 8. 更新 template_source.last_synced
```

---

## 五、Skill 创建 AI 队友流程

### 5.1「Skill 设计师」模板

作为第 9 个系统模板（本地模板，`my-templates/skill-creator.md`）：

```yaml
---
name: skill-creator
description: Guide for creating effective skills through multi-turn conversation
model: sonnet
---

## Purpose
你是 AgentHub 平台的 Skill 设计师助手。通过多轮对话，帮用户创建高质量的 SKILL.md。

## Behavioral Traits
- 每轮只问一个问题，不连珠炮
- 用户回答后简短确认，再进入下一问
- 用户跑题时温和引导回 skill 定义
- 用户连续 2 次简短回复，给出 3 个选项引导

## Response Approach
### Phase 1 — 探索（逐一提问）
1. 核心功能：「这个 skill 要解决什么问题？一句话描述。」
2. 触发场景：「用户在什么情况下会用到？给 3-5 个触发词。」
3. 执行步骤：「执行流程、约束条件、输出格式？」
4. 使用示例：「给 1-2 个具体例子（输入→期望输出）。」
5. 特殊约束：「绝对不能做的事？必须引用的外部知识？」

### Phase 2 — 草稿生成
生成完整 SKILL.md（markdown 代码块），询问是否满足需求。

### Phase 3 — 修改循环（最多 3 轮）

### Phase 4 — 最终确认
用户确认后，通过 Write 工具保存到 {SKILLS_DIR}/{slug}/SKILL.md

## Constraints & Boundaries
- SKILL.md 的 name 必须是 kebab-case 英文 slug（≤40 字符）
- description 必须用中文（≤200 字符）
- triggers 必须是中文短词（3-7 个）
- 一次只创建一个 skill
- 每次输出 SKILL.md 必须用 ```markdown 代码块包裹
```

### 5.2 对话保存检测

```
CLI Agent 通过 Write tool 写入文件
    │
    ▼
前端轮询 GET /api/skills/library（每 5s，最多 30s）
    │
    ├── 检测到新 skill → toast「Skill 已创建」+ 刷新列表 + 结束轮询
    │
    └── 30s 超时 → 降级：从对话消息解析 SKILL.md
                    → POST /api/skills/library/create
                    → 成功 → 刷新列表
```

### 5.3 边界

| 场景 | 处理 |
|------|------|
| CLI 中途崩溃 | 对话消息已持久化，重启 CLI → 恢复会话 → Agent 从 Phase 1 重新引导（跳过已回答的问题） |
| 用户连续 2 次简短回复 | Agent 给出 3 个具体选项：「你是想做 A（标题生成）、B（代码审查）、还是 C（文档写作）？」 |
| 用户输入「取消」 | Agent 确认：「好的，skill 创建已取消。你可以随时重新开始。」 |
| Agent 生成的 SKILL.md 格式不对 | 前端检测到非标准格式 → 不显示保存按钮 → 显示「格式似乎有问题，让 Agent 重新生成？」提示 |

---

## 六、边界设计与风险

### 6.1 模板生命周期

| 场景 | 处理 |
|------|------|
| 新增模板（本地） | `POST /api/templates` → `my-templates/*.md` + DB |
| 编辑模板（本地） | `PATCH /api/templates/{id}` → 更新 .md 文件 + DB |
| 删除模板（本地） | `DELETE /api/templates/{id}` → 删除 .md 文件 + DB 行。检查 Agent 引用，警告不阻止 |
| 模板→Agent 快照 | 创建 Agent 时复制所有模板字段。`created_from_template_id` 记录来源 |
| 模板源同步 | git pull → 重新扫描 → 增量更新 DB |

### 6.2 模板源管理

| 场景 | 处理 |
|------|------|
| 网络不可用/仓库无法访问 | 已有 clone 可继续使用；同步失败展示错误 + 上次同步时间 |
| 仓库格式变更 | 解析器容错：缺失非必填字段不报错，仅跳过该模板 |
| 仓库中模板数量变化 | 增量更新：新增 → INSERT / 修改 → UPDATE / 删除 → soft DELETE |

### 6.3 迁移策略

1. 8 个中文模板迁移为本地模板（`my-templates/`），保留兼容
2. 新增「Skill 设计师」作为第 9 个本地模板
3. wshobson/agents clone 后提供 192 个英文模板
4. ~40 个高频模板有中文翻译
5. 前端保留增强版 TEMPLATES 数组作为 fallback

---

## 七、实施路线图

### Phase 1: 后端基础设施（当前）

| # | 任务 | 预估 |
|---|------|------|
| 1.1 | 术语决议 — Agent「蓝图」vs MCP「模板」对外名称 | 0.5h |
| 1.2 | 编写 spec → Review → 冻结 | 2h |
| 1.3 | Alembic migration（templates + template_source 表 + agents 新增列） | 2h |
| 1.4 | `git_manager.py`：clone/pull/validate | 3h |
| 1.5 | `parser.py`：YAML frontmatter + 章节提取 | 2h |
| 1.6 | Domain + Infrastructure（Template 实体 + ORM + Repository） | 3h |
| 1.7 | Application（TemplateService：CRUD + 同步 + 导出） | 4h |
| 1.8 | Schema + API（8 个端点） | 3h |
| 1.9 | 40 个模板中文翻译数据 + 9 个本地模板 seed | 3h |
| 1.10 | model tier 映射表（前端 matrix 扩展 + 后端） | 2h |
| 1.11 | 修复已有缺陷（capability_tags / system_prompt / Skill 删除引用检查） | 2h |
| 1.12 | 后端测试 | 3h |

### Phase 2: 前端模板选择 + Skill 创建

| # | 任务 | 预估 |
|---|------|------|
| 2.1 | `templateStore.ts` | 2h |
| 2.2 | `TemplateGrid` + `TemplateCard` + `TemplatePreviewPanel` | 5h |
| 2.3 | 重构 `CreateAgentModal.tsx` Step 1（API 动态加载 + fallback） | 4h |
| 2.4 | 模板管理 Tab（SkillMarketplacePage 第 3 Tab） | 4h |
| 2.5 | `CreateSkillDialog.tsx`（三路径：快速/AI生成/AI助手引导） | 3h |
| 2.6 | `SkillCreationWizard.tsx`（引导路径入口） | 2h |
| 2.7 | `MessageBubble` 增强（SKILL.md 检测 + 预览面板 + 保存） | 3h |
| 2.8 | 兼容性过滤（Step 2 不兼容 CLI 置灰） | 2h |
| 2.9 | 集成测试 | 3h |

### Phase 3: 打磨

| # | 任务 | 预估 |
|---|------|------|
| 3.1 | 全状态覆盖审计（loading/empty/error） | 2h |
| 3.2 | 用户文档 | 2h |
| 3.3 | E2E（模板同步→选择→创建 Agent→验证 system_prompt） | 3h |
| 3.4 | E2E（Skill 设计师→对话→预览→保存→Skill 可用） | 3h |

---

## 附录：已确认的设计决策

| 决策 | 结论 |
|------|------|
| 模板格式 | wshobson/agents 原生 agent markdown |
| 模板来源 | wshobson/agents 唯一（MVP） |
| 存储 | 文件系统（Git 仓库）+ DB 索引 |
| 模板目录 | 独立 `.agenthub/templates/` |
| Agent 关系 | 创建时快照 |
| 中文翻译 | 手动翻译 ~40 个高频模板 |
| pi_agent 兼容 | system_prompt 直接通过 `--system-prompt` 传入，完全兼容 |
| 对话式创建 Skill | **当期做** |
| 对话式创建模板 | 推迟（post-MVP） |
| GitHub private repo | 推迟（post-MVP） |
| 多 GitHub 源 | 推迟（post-MVP） |
