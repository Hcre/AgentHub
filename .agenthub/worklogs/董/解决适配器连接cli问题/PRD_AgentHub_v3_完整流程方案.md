# AgentHub PRD v3.0 — 完整流程方案（⚠️ 已废弃）

> ⚠️ **v4 已取代**。请阅读 `PRD_AgentHub_v4_统一方案.md`。
> 本文件保留为历史参考，不再维护。与 ADR-01 的冲突裁决见 v4 §一。
>
> 基于社区调研 + 架构对比分析 + 当前代码审计 | 2026-05-23

---

## 一、产品定义

IM 聊天式多 Agent 协作平台。用户创建 Agent（选系统 + 配模型 + 设 System Prompt / Skills 卡片）、拉群、像飞书一样 @Agent 下达任务。简单对话走 SDK 模式（轻量），复杂 coding 任务走 CLI 子进程模式（完整工具生态）。协调者自动分解、分派、合并结果。代码 Diff、网页预览在聊天流中内联展示。

### 核心决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 接入 | **SDK + CLI 双模式** | SDK 适合简单对话（轻量），CLI 适合复杂 coding（完整工具生态） |
| IM 展示 | **自建 React Web 前端** | 比赛 Demo 需要 Diff/Preview/审批卡片的自定义渲染 |
| IM 消息管道 | **可选飞书 Bot 管道** | 复用飞书消息推送和移动端可达性，Web 端做富展示 |
| 多 Agent 编排 | **Coordinator 分解 + asyncio 并发** | 保留 LLM 驱动分解，砍掉 Celery DAG，改用 asyncio.gather |
| 记忆系统 | **L1 滑动窗口 + L2 摘要，CLI 自管对话内** | 分层不冲突 |

---

## 二、最终架构（简化版）

```
┌─────────────────────────────────────────────────────────────────┐
│  L5  Presentation（React + TypeScript）                          │
│                                                                   │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ ChatView │ │AgentCreate│ │TaskBoard │ │ GroupChat (群聊)   │  │
│  │ 单聊窗口  │ │ 卡片式配置 │ │ 任务看板  │ │ @mention 路由      │  │
│  │ · 流式   │ │ · Agent系统│ │ · 状态   │ │ · Coordinator卡片 │  │
│  │ · Diff   │ │ · Provider│ │ · 产物   │ │ · Worker结果聚合  │  │
│  │ · Preview│ │ · Model   │ │          │ │                    │  │
│  │ · 审批   │ │ · Skills  │ │          │ │                    │  │
│  └──────────┘ │ · SysPrmpt│ └──────────┘ └──────────────────┘  │
│               └───────────┘                                       │
│  Stores: chatStore / agentStore / groupStore / taskStore          │
│  Hooks: useWebSocket / useStreaming / useContext                   │
└──────────────────────────────┬────────────────────────────────────┘
                               │ WS + REST
┌──────────────────────────────┴────────────────────────────────────┐
│  L4  API Gateway（FastAPI）                                        │
│  /api/agents  /api/groups  /api/sessions  /api/tasks  /ws/sessions│
└──────────────────────────────┬────────────────────────────────────┘
                               │ Command
┌──────────────────────────────┴────────────────────────────────────┐
│  L3  Application                                                  │
│  AgentService / GroupService / ChatService / TaskService           │
│  CoordinatorService (LLM分解 → asyncio.gather并发执行)              │
└──────────────────────────────┬────────────────────────────────────┘
                               │ Domain Object
┌──────────────────────────────┴────────────────────────────────────┐
│  L2  Domain                                                       │
│  Agent / Group / Session / Message / Task (聚合根)                 │
│  TaskFSM (8状态) / Coordinator / Harness (校验+环检测)             │
│  StreamEvent 协议 / UnifiedAgent ABC                               │
└──────────┬────────────────────────────────────────────────────────┘
           │ Repository / Adapter Interface
┌──────────┴────────────────────────────────────────────────────────┐
│  L1  Infrastructure                                                │
│                                                                     │
│  PG (6表)      Redis (L1记忆)     LLM Adapters                     │
│  · agents      · sliding window   ┌──────────────────────┐        │
│  · groups      · pub/sub         │ ClaudeAdapter (SDK)   │        │
│  · members     · rate limit      │ → Anthropic Messages  │        │
│  · sessions                      │    API 流式            │        │
│  · messages                      ├──────────────────────┤        │
│  · tasks                         │ ClaudeCLIAdapter      │        │
│                                  │ → spawn 子进程         │        │
│  L1 Memory (Redis)               │ → 独立 env vars       │        │
│  · 滑动窗口 20条                  │ → 独立 work dir       │        │
│  · 按 session_id 隔离             │ → 完整工具生态         │        │
│                                  └──────────────────────┘        │
│  Session 文件存储（CLI模式）                                       │
│  /tmp/agenthub/sessions/{agent_id}/                               │
│    ├── CLAUDE.md （项目上下文 + 记忆注入）                          │
│    └── .claude/skills/ （Skills 文件）                             │
└────────────────────────────────────────────────────────────────────┘
```

### 表精简：12 → 6

| 表 | 保留? | 说明 |
|----|------|------|
| `agents` | 保留 | 核心。`capability_tags` 用数组字段，不拆表。`skills` 存 skill 名称列表 |
| `groups` | 保留 | 核心 |
| `group_members` | 保留 | 核心 |
| `sessions` | 保留 | 核心。长对话摘要存 `summary` 字段 |
| `messages` | 保留 | 核心。消息持久化 |
| `tasks` | 保留 | 核心。`status` 字段替代 task_events 表 |
| ~~`agent_capabilities`~~ | 砍掉 | 合并到 agents 的 `capability_tags TEXT[]` |
| ~~`task_events`~~ | 砍掉 | 事件溯源在 Demo 中不可见，task.status 字段够用 |
| ~~`task_artifacts`~~ | 砍掉 | 用文件系统 `/tmp/agenthub/artifacts/{task_id}/` |
| ~~`notifications`~~ | 砍掉 | WS 实时推送，不需要持久化通知表 |
| ~~`deploy_logs`~~ | 砍掉 | M5 不做 deploy |
| ~~`users`~~ | 砍掉 | 单用户 Demo，不需要 |

---

## 三、Agent 接入：SDK + CLI 双模式详解

### 3.1 两种模式的定位

| | SDK 模式 (ClaudeAdapter) | CLI 模式 (ClaudeCLIAdapter) |
|---|---|---|
| **适用场景** | 简单问答、Coordinator 分解、记忆检索 | 复杂 coding（读写文件、git、bash、部署） |
| **工具能力** | 仅 function calling 定义的 9 个 Tool | Claude Code 内置 55+ 工具 + MCP + Skills |
| **启动方式** | HTTP API 调用 | spawn 子进程，stdin/stdout pipe |
| **资源占用** | 轻量，一个 HTTP 连接 | 每个 session 一个子进程 |
| **状态管理** | 无状态，每次调用传完整上下文 | 有状态，session 存 JSONL 文件 |
| **实现状态** | 已实现 (`claude_adapter.py`) | 待实现 (factory.py 有占位) |

### 3.2 单机多 Agent 不同配置

同一台电脑可同时运行多个不同配置的 Claude Code。每个子进程通过**独立环境变量**控制：

```python
# Agent "前端专家" → 用 DeepSeek 模型
Agent "FrontendExpert":
  env: {
    ANTHROPIC_API_KEY=sk-deepseek-xxx,
    ANTHROPIC_BASE_URL=http://localhost:3457/v1,  # LiteLLM Proxy
    ANTHROPIC_MODEL=deepseek-v3,
  }
  cli_args: --system-prompt "你是前端专家"
  work_dir: /tmp/agenthub/sessions/frontend-expert/

# Agent "后端专家" → 用 Claude Sonnet
Agent "BackendExpert":
  env: {
    ANTHROPIC_API_KEY=sk-ant-xxx,
    ANTHROPIC_MODEL=claude-sonnet-4-20250514,
  }
  cli_args: --system-prompt "你是后端专家"
  work_dir: /tmp/agenthub/sessions/backend-expert/

# Agent "Reviewer" → 用 Qwen（通过 LiteLLM 中转）
Agent "Reviewer":
  env: {
    ANTHROPIC_API_KEY=sk-qwen-xxx,
    ANTHROPIC_BASE_URL=http://localhost:3457/v1,
    ANTHROPIC_MODEL=qwen-max,
  }
  cli_args: --system-prompt "你是代码审查专家"
  work_dir: /tmp/agenthub/sessions/reviewer/
```

**LiteLLM Proxy 的作用**：当用户选非 Anthropic 模型时，AgentHub 自动启动一个本地 LiteLLM 子进程做格式转换（Anthropic Messages ↔ OpenAI Chat）。AgentHub 的 `base_url` 字段指向 `localhost:3457`。

### 3.3 Skills 的卡片式设置

Skills 不属于 API 参数，是文件系统中的 `.md` 文件。Claude Code CLI 启动时自动加载 `work_dir/.claude/skills/` 目录下的所有 skill 文件。

**创建 Agent 时的 Skills 卡片**：

```
┌── 新建 Agent ──────────────────────────────┐
│                                              │
│  Agent 名称  [________________]              │
│  Agent 系统  ○ Claude Code  ○ Codex          │
│  Provider   [DeepSeek          ▼]           │
│  Model      [deepseek-v3       ▼]           │
│  API Key    [••••••••••••••••]              │
│                                              │
│  ┌── System Prompt ──────────────────────┐  │
│  │ 你是前端开发专家，擅长 React +          │  │
│  │ TypeScript。代码风格遵循 Airbnb 规范。  │  │
│  │ 所有组件使用 Tailwind CSS。            │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  ┌── Skills ─────────────────────────────┐  │
│  │ ☑ frontend-design    ☐ deploy         │  │
│  │ ☑ code-review        ☐ security-review│  │
│  │ ☑ paper-2-web        ☑ skill-creator  │  │
│  │ ☐ notebooklm         ☑ xlsx           │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  ┌── 权限模式 ───────────────────────────┐  │
│  │ ○ 正常模式 (危险操作需审批)            │  │
│  │ ● 自动模式 (全自动，跳过审批)          │  │
│  └───────────────────────────────────────┘  │
│                                              │
│          [创建 Agent]                        │
└──────────────────────────────────────────────┘
```

**后端保存逻辑**：

```python
# AgentService.create()
async def create(self, cmd: CreateAgentCommand) -> Agent:
    agent = Agent(
        name=cmd.name,
        agent_system=cmd.agent_system,    # "claude" / "codex"
        provider=cmd.provider,            # "deepseek" / "anthropic" / ...
        model=cmd.model,
        api_key_encrypted=encrypt(cmd.api_key),
        system_prompt=cmd.system_prompt,
        skills=cmd.skills,                # ["frontend-design", "code-review"]
        permission_mode=cmd.permission_mode,  # "default" / "yolo"
    )

    # CLI 模式预置 skill 文件
    if cmd.agent_system == "claude":
        skill_dir = f"/tmp/agenthub/sessions/{agent.id}/.claude/skills/"
        for skill_name in cmd.skills:
            copy_skill_file(skill_name, skill_dir)

        # 写入 CLAUDE.md（项目上下文 + system prompt 扩展）
        write_claude_md(agent.work_dir, agent.system_prompt)

    await self.agent_repo.save(agent)
    return agent
```

### 3.4 ClaudeCLIAdapter 实现

```python
# backend/app/infrastructure/llm/claude_cli_adapter.py (M2 新增)
import asyncio
import json
import os
from pathlib import Path
from app.domain.llm.protocol import (
    AgentRequest, StreamEvent, StreamEventType, UnifiedAgent,
)


class ClaudeCLIAdapter(UnifiedAgent):
    """CLI 子进程模式：完整 Claude Code 工具生态。"""

    def __init__(self, agent_config: dict) -> None:
        self.agent_id = str(agent_config["id"])
        self.env = {
            "ANTHROPIC_API_KEY": decrypt(agent_config["api_key_encrypted"]),
            "ANTHROPIC_BASE_URL": agent_config.get("base_url") or "",
            "ANTHROPIC_MODEL": agent_config["model"],
            "CLAUDE_CODE_SKIP_DOTENV": "1",
        }
        self.system_prompt = agent_config.get("system_prompt") or ""
        self.permission_mode = agent_config.get("permission_mode", "default")
        self.work_dir = Path(f"/tmp/agenthub/sessions/{self.agent_id}")
        self.work_dir.mkdir(parents=True, exist_ok=True)

    async def stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        # 注入首次上下文到 CLAUDE.md（仅在 session 开始时）
        await self._inject_memory(request)

        args = [
            "claude",
            "--system-prompt", self.system_prompt,
            "--permission-mode", self.permission_mode,
            "--output-format", "stream-json",
            "-p", request.messages[-1]["content"],  # 最后一条用户消息
        ]

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(self.work_dir),
            env={**os.environ, **self.env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        seq = 0
        async for line in proc.stdout:
            try:
                data = json.loads(line)
                event = self._parse_claude_event(data, seq)
                seq += 1
                yield event
            except json.JSONDecodeError:
                continue

        yield StreamEvent(type=StreamEventType.DONE, seq=seq)

    async def _inject_memory(self, request: AgentRequest) -> None:
        """仅在 session 首次创建时注入跨会话上下文到 CLAUDE.md。"""
        claude_md = self.work_dir / "CLAUDE.md"
        if claude_md.exists():
            return  # 已注入过，不重复写入

        memory = request.memory
        lines = ["# AgentHub Context (injected on session start)\n"]
        if memory and memory.l2_summary:
            lines.append(f"## 历史对话摘要\n{memory.l2_summary}\n")
        if memory and memory.l3_specs:
            lines.append(f"## 项目上下文\n{memory.l3_specs}\n")

        claude_md.write_text("\n".join(lines), encoding="utf-8")

    def _parse_claude_event(self, data: dict, seq: int) -> StreamEvent:
        """将 Claude CLI JSON 输出映射为 StreamEvent。"""
        msg_type = data.get("type", "")
        if msg_type == "assistant":
            return StreamEvent(
                type=StreamEventType.TEXT,
                seq=seq,
                content=data.get("message", {}).get("content", ""),
            )
        elif msg_type == "tool_use":
            return StreamEvent(
                type=StreamEventType.TOOL_CALL,
                seq=seq,
                tool_call={"name": data.get("name"), "arguments": data.get("input", {})},
            )
        # ... 其他类型映射
        return StreamEvent(type=StreamEventType.TEXT, seq=seq, content="")

    async def chat_structured(self, prompt: str) -> dict:
        """CLI 模式不支持结构化输出，回退到 SDK 模式。Coordinator 用 SDK。"""
        raise NotImplementedError("CLI 模式不支持 chat_structured，请使用 SDK 模式做 Coordinator")
```

---

## 四、完整流程 Walkthrough

### 流程零：环境准备

```
docker compose up -d postgres redis   # 启动 PG + Redis
make dev                              # 启动 FastAPI + Vite
```

用户打开浏览器 `http://localhost:5173`。

---

### 流程一：创建 Agent（卡片式配置）

**第一步：用户进入 Agent 管理页面，点击「新建 Agent」**

系统支持两种创建方式：
- **表单式**：直接填表（快速）
- **对话式**：自然语言描述 → 系统生成 System Prompt 草案 + 推荐 Skills → 用户确认（智能）

**第二步：填写 Agent 卡片**

```
表单内容：
  Agent 名称: "前端专家"
  Agent 系统: Claude Code     ← 选 CLI 模式（完整工具生态）
  Provider:   DeepSeek        ← 实际模型厂商
  Model:      deepseek-v3     ← 模型名
  Base URL:   http://localhost:3457/v1  ← LiteLLM 代理地址（非 Anthropic 时必填）
  API Key:    sk-deepseek-xxx
  System Prompt: "你是前端开发专家，擅长 React + TypeScript + Tailwind CSS"
  Skills:     ☑ frontend-design  ☑ code-review  ☐ deploy  ☐ skill-creator
  权限模式:   ● 正常模式 (危险操作需审批)
```

**第三步：后端处理**

```python
# AgentService.create()
# 1. 校验 name 唯一性
# 2. AES-256-GCM 加密 API Key
# 3. 创建 Agent 聚合根
# 4. 如果 agent_system == "claude":
#    → 创建 work_dir: /tmp/agenthub/sessions/{agent_id}/
#    → 写入 CLAUDE.md (含 system_prompt)
#    → 复制选中的 skill 文件到 .claude/skills/
# 5. 持久化到 agents 表
# 6. 发布 AgentCreated 事件
```

**第四步：用户再创建一个「后端专家」Agent**

```
Agent 名称: "后端专家"
Agent 系统: Claude Code
Provider:   Anthropic       ← 直连，不需要 LiteLLM
Model:      claude-sonnet-4-20250514
API Key:    sk-ant-xxx
System Prompt: "你是后端开发专家，擅长 FastAPI + PostgreSQL + Redis"
Skills:     ☑ code-review  ☐ frontend-design  ☑ deploy
权限模式:   ● 正常模式
```

**第五步：用户创建一个「代码审查」Agent**

```
Agent 名称: "代码审查员"
Agent 系统: Claude Code
Provider:   Zhipu           ← 通过 LiteLLM 中转
Model:      glm-4
Base URL:   http://localhost:3457/v1
API Key:    sk-zhipu-xxx
System Prompt: "你是代码审查专家，遵循 Google Code Review 标准"
Skills:     ☑ code-review  ☑ security-review
权限模式:   ● 正常模式
```

**此刻 agents 表状态**：

```
| id | name      | agent_system | provider   | model                    | skills                    | permission_mode |
|----|-----------|-------------|------------|--------------------------|---------------------------|-----------------|
| a1 | 前端专家   | claude      | deepseek   | deepseek-v3              | [frontend-design,code-review] | default     |
| a2 | 后端专家   | claude      | anthropic  | claude-sonnet-4-20250514 | [code-review,deploy]      | default         |
| a3 | 代码审查员 | claude      | zhipu      | glm-4                    | [code-review,security-review] | default     |
```

---

### 流程二：创建群聊（自动生成 Coordinator）

**第一步：点击「创建群组」**

```
群组名称: "全栈开发组"
描述: "前后端协作开发群"
初始成员: ☑ 前端专家  ☑ 后端专家  ☑ 代码审查员
```

**第二步：后端处理**

```python
# GroupService.create()
# 1. 创建 Group(id=g1, name="全栈开发组")
# 2. 自动创建 Coordinator Agent:
#    Agent(
#      name="协调者-全栈开发组",
#      role="system_coordinator",
#      agent_system="claude",        # Coordinator 用 SDK 模式（轻量）
#      provider=settings.coordinator_provider,  # 系统默认，如 anthropic
#      model=settings.coordinator_model,        # 如 claude-haiku-4-5（便宜）
#      is_system=True,
#      system_prompt="你是任务协调者。将用户需求分解为子任务，分配给群内 Agent...",
#      skills=[],
#      permission_mode="default",
#    )
# 3. 把初始成员 + Coordinator 加入 group_members
# 4. 发布 GroupCreated + AgentCreated(coordinator)
```

**此刻 groups + group_members 表状态**：

```
groups:
| id | name        | coordinator_config                    |
|----|------------|--------------------------------------|
| g1 | 全栈开发组  | {model: "claude-haiku-4-5", ...}     |

group_members:
| group_id | agent_id | role               |
|----------|---------|--------------------|
| g1       | a1      | member (前端专家)    |
| g1       | a2      | member (后端专家)    |
| g1       | a3      | member (代码审查员)  |
| g1       | c1      | coordinator        |
```

**第三步：群聊在前端显示**

```
┌── 全栈开发组 ──────────────────────────────────────────┐
│ 成员列表                        │ 聊天区域              │
│ ┌──────────────────────────┐   │                      │
│ │ ● 前端专家    [deepseek] │   │                      │
│ │ ● 后端专家    [claude]   │   │  (空，等待第一条消息)   │
│ │ ● 代码审查员  [glm-4]    │   │                      │
│ │ ◈ 协调者      [system]   │   │                      │
│ └──────────────────────────┘   │                      │
│                                 │                      │
│ [添加成员] [群组设置]           │ [输入消息...]  [发送] │
└─────────────────────────────────────────────────────────┘
```

---

### 流程三：群聊实际对话（完整链路）

这是整个系统最核心的流程。场景：用户在群里发一条任务消息。

#### Step 1：用户发送消息

```
用户在群聊输入框输入：
"帮我做一个用户登录功能，包含前端登录页面和后端 /api/auth/login 接口"

按 Enter 发送。
```

#### Step 2：前端处理

```typescript
// MessageInput.tsx → useWebSocket.ts
ws.send(JSON.stringify({
  type: "message",
  content: "帮我做一个用户登录功能，包含前端登录页面和后端 /api/auth/login 接口",
  mentions: [],  // 没有 @具体人 → auto 模式
  dispatch_mode: "auto",
}));
```

#### Step 3：后端 ChatService 接收

```python
# chat_service.py → send_and_stream()
# 1. 持久化用户消息到 messages 表
# 2. 写入 L1 Redis 滑动窗口
# 3. 判定 dispatch_mode:
#    "auto" + 无 @mention → 检查是否包含任务意图

# 4. 意图检测（轻量 LLM 调用或关键词匹配）
intent = await self._detect_intent(cmd.content)
# → intent = "task"（包含"帮我做"/"创建"/"实现"等任务关键词）
```

#### Step 4：触发 Coordinator 分解

```python
# CoordinatorService.decompose_and_dispatch()
coordinator_agent = await self._get_coordinator(group_id)

# Coordinator LLM 调用（用 SDK 模式，轻量）
plan = await coordinator.decompose(
    message="帮我做一个用户登录功能，包含前端登录页面和后端 /api/auth/login 接口",
    available_agents=[
        {"name": "前端专家", "id": "a1", "capabilities": ["react", "typescript", "css"]},
        {"name": "后端专家", "id": "a2", "capabilities": ["python", "fastapi", "postgresql"]},
        {"name": "代码审查员", "id": "a3", "capabilities": ["code_review", "testing"]},
    ],
)

# Coordinator 返回结构化 JSON:
# {
#   "action": "decompose_and_dispatch",
#   "plan": {
#     "tasks": [
#       {"id": "task-1", "intent": "ui", "description": "创建登录页面 UI 组件",
#        "suggested_worker": "前端专家", "depends_on": []},
#       {"id": "task-2", "intent": "api", "description": "创建 POST /api/auth/login 接口",
#        "suggested_worker": "后端专家", "depends_on": []},
#       {"id": "task-3", "intent": "review", "description": "审查前后端代码",
#        "suggested_worker": "代码审查员", "depends_on": ["task-1", "task-2"]}
#     ]
#   }
# }
```

#### Step 5：Harness 校验 + 路由

```python
# Harness.validate(plan)
# 1. detect_cycle(plan) → False ✓ (无循环依赖)
# 2. route_worker:
#    task-1 → 前端专家 (a1) ✓ (能力匹配)
#    task-2 → 后端专家 (a2) ✓ (能力匹配)
#    task-3 → 代码审查员 (a3) ✓ (能力匹配)
# 3. 创建父任务 + 3 个子任务，写入 tasks 表
```

#### Step 6：并发执行（asyncio.gather 替代 Celery）

```python
# 无依赖的 task-1 和 task-2 并行执行
tasks.task-1 → 前端专家 (a1) → CLI 子进程，写 React 代码
tasks.task-2 → 后端专家 (a2) → CLI 子进程，写 FastAPI 代码

# 两者都完成后，task-3 执行
tasks.task-3 → 代码审查员 (a3) → CLI 子进程，审查代码

# Worker 执行逻辑（M2 为同步，M3 加 asyncio 并发）
async def execute_task(task, agent, session_context):
    # 1. FSM: PENDING → RUNNING
    task.transition(RUNNING)

    # 2. 构造上下文
    context = build_agent_context(task, session_context)

    # 3. 选择适配器模式
    if agent.agent_system == "claude" and task.complexity == "high":
        # CLI 模式：spawn 子进程，获得完整工具生态
        adapter = ClaudeCLIAdapter(agent.config)
    else:
        # SDK 模式：轻量对话
        adapter = ClaudeAdapter(agent.api_key, agent.model)

    # 4. 流式执行
    request = AgentRequest(
        messages=[{"role": "user", "content": task.description}],
        memory=context,
    )
    async for event in adapter.stream(request):
        # 每个 token 通过 Redis Pub/Sub → WS → 前端
        yield event

    # 5. FSM: RUNNING → COMPLETED
    task.transition(COMPLETED)
```

#### Step 7：前端实时显示

```
┌── 全栈开发组 ──────────────────────────────────────────────┐
│                                                             │
│ 👤 用户                                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 帮我做一个用户登录功能，包含前端登录页面和后端            │ │
│ │ /api/auth/login 接口                                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ◈ 协调者                                                     │
│ ┌── 任务分解 ────────────────────────────────────────────┐  │
│ │ 📋 已分解为 3 个子任务:                                 │  │
│ │                                                         │  │
│ │ task-1: 创建登录页面 UI 组件                             │  │
│ │   → 前端专家 [进行中 ████████░░]                         │  │
│ │                                                         │  │
│ │ task-2: 创建 POST /api/auth/login 接口                  │  │
│ │   → 后端专家 [进行中 ██████░░░░]                         │  │
│ │                                                         │  │
│ │ task-3: 审查前后端代码                                   │  │
│ │   → 代码审查员 [等待前序任务...]                         │  │
│ └─────────────────────────────────────────────────────────┘  │
│                                                             │
│ ● 前端专家 (task-1 执行中)                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 我来创建登录页面。                                       │ │
│ │                                                         │ │
│ │ ```tsx                                                  │ │
│ │ // LoginPage.tsx                                        │ │
│ │ export function LoginPage() {                           │ │
│ │   const [email, setEmail] = useState('');               │ │
│ │ █  (流式生成中...)                                       │ │
│ │ ```                                                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ● 后端专家 (task-2 执行中)                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 我来创建登录 API...                                      │ │
│ │ █ (流式生成中...)                                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [输入消息...]                                     [发送]    │
└─────────────────────────────────────────────────────────────┘
```

#### Step 8：执行完成，产物汇总

```
● 代码审查员 (task-3 完成)
┌─────────────────────────────────────────────────────┐
│ 审查完成。                                            │
│                                                      │
│ 📊 前端代码 (LoginPage.tsx)                           │
│   ✅ 组件结构合理，使用 Tailwind CSS                  │
│   ⚠️ 建议添加表单验证                                  │
│   [查看 Diff]                                        │
│                                                      │
│ 📊 后端代码 (auth.py)                                 │
│   ✅ API 设计符合 RESTful 规范                        │
│   ✅ JWT 实现正确                                     │
│   ⚠️ 建议添加 rate limiting                           │
│   [查看 Diff]                                        │
│                                                      │
│ 综合评分: 8.5/10，建议合并                            │
└─────────────────────────────────────────────────────┘
```

---

### 流程四：记忆系统如何工作（分层不冲突）

```
┌─────────────────────────────────────────────────────────────────┐
│                       记忆分工边界                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AgentHub 记忆系统 (外部注入)                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ L1 Redis 滑动窗口 (最近 20 条消息全文)                    │     │
│  │   · SDK 模式：每次调用注入到 AgentRequest               │     │
│  │   · CLI 模式：仅在首次 session 创建时注入                │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │ L2 PG 摘要 (长对话压缩)                                  │     │
│  │   · 对话 > 20 条时触发压缩                               │     │
│  │   · 摘要写入 session.summary 字段                        │     │
│  │   · CLI 模式：注入到 CLAUDE.md 的"历史对话摘要"段         │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │ L3 项目上下文 (.agenthub/)  [M4-M5 可选]                │     │
│  │ L4 pgvector RAG 检索 [M4-M5 可选]                       │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Claude Code CLI 内存 (进程内，自动管理)                          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ 对话历史 (messages[] 数组)                               │     │
│  │   · CLI 内部自动维护                                     │     │
│  │   · /compact 压缩                                        │     │
│  │   · 从 JSONL session 文件读写                            │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │ CLAUDE.md 文件                                           │     │
│  │   · CLI 启动时自动加载                                   │     │
│  │   · AgentHub 在 session 创建时写入一次                    │     │
│  │   · 后续 CLI 自己可以修改（如 /init 命令）               │     │
│  ├────────────────────────────────────────────────────────┤     │
│  │ Skills 文件 (.claude/skills/)                            │     │
│  │   · CLI 启动时自动加载                                   │     │
│  │   · AgentHub 在 Agent 创建时写入                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**关键原则**：
- CLI 自己管理"对话内"状态（messages 数组、当前上下文）
- AgentHub 管理"跨会话"状态（会话摘要、项目上下文）
- AgentHub 只在 **session 创建时注入一次**，后续不干预 CLI 内部状态
- 两个系统通过 **文件系统**（CLAUDE.md、JSONL session 文件）交换信息，互不覆盖

---

### 流程五：Loop Guard（防止 Agent 无限互聊）

```python
# Harness 增加 loop guard
class LoopGuard:
    def __init__(self, max_consecutive_agent_messages=5):
        self.max_consecutive = max_consecutive_agent_messages

    def check(self, recent_messages: list[Message]) -> bool:
        """检测最近 N 条是否全是 Agent 发送且互相 @。"""
        agent_count = 0
        for msg in reversed(recent_messages):
            if msg.role == "assistant" and msg.mentions:
                agent_count += 1
            else:
                break
        if agent_count >= self.max_consecutive:
            # 强制静默 30 秒
            return False  # 不允许继续发送
        return True
```

---

## 五、IM 管道：可选飞书 Bot + Web 前端

如果时间和场景需要，可以在不修改 Web 前端代码的情况下增加飞书消息管道：

```
                    飞书 App                       浏览器 Web
                       │                              │
            @Agent 发消息                             │
              │                                      │
              ▼                                      │
         飞书 Bot Webhook                             │
              │                                      │
              │ POST /api/feishu/webhook             │
              │ {chat_id, user_id, text, mentions}    │
              │                                      │
              ▼                                      ▼
         ┌─────────────────────────────────────────────┐
         │        AgentHub 后端 (统一消息总线)           │
         │                                             │
         │  ChatService.send_and_stream()               │
         │  · 同一个 ChatService 处理所有来源             │
         │  · 通过 source 字段标记消息来源               │
         │                                             │
         │  返回:                                      │
         │  · 简单文本 → 直推飞书消息卡片                 │
         │  · 富内容(Diff/Preview) → 飞书通知 + Web链接  │
         │  · 全部内容 → WebSocket 推 Web 端            │
         └─────────────────────────────────────────────┘
```

**飞书适配器（~200行）**：

```python
# adapters/feishu_adapter.py
class FeishuAdapter:
    """管道模式：飞书 ↔ AgentHub。不替代 Web 前端。"""

    async def on_message(self, event: FeishuEvent):
        # 飞书消息 → SendMessageCommand → ChatService（跟 Web 端同一条链路）
        cmd = SendMessageCommand(
            session_id=self.resolve_session(event.chat_id),
            content=event.text,
            mentions=parse_mentions(event.text),
            source="feishu",
        )
        async for event in self.chat.send_and_stream(cmd):
            if event.type == StreamEventType.DONE:
                # Agent 回复完成 → 推送到飞书
                await self._push_to_feishu(event)

    async def _push_to_feishu(self, result):
        if result.has_rich_content:
            # 富内容 → 飞书发摘要 + Web 链接
            await self.feishu.send_card(
                chat_id=result.chat_id,
                title="📋 任务完成",
                body=f"{result.summary}\n\n🔗 [查看详情]({result.web_url})"
            )
        else:
            # 纯文本 → 直接发
            await self.feishu.send_text(result.chat_id, result.text)
```

**Web 前端不受影响**。飞书只是多了一个消息入口和一个简化的通知出口。

---

## 六、精简后的里程碑计划

| 里程碑 | 时间 | 核心交付 | 砍掉的内容 |
|--------|------|---------|-----------|
| **M1** 环境+验证 | 5/20-22 (已完成) | 脚手架 + SDK ClaudeAdapter 流式跑通 + PG/Redis | — |
| **M2** 单聊 MVP | 5/23-27 (当前) | SDK + CLI 双模式，Agent 卡片式创建，Skills 选择，1v1 私聊，流式渲染 | Celery、pgvector、Repository 接口层 |
| **M3** 群聊+协调者 | 5/28-6/1 | 群组创建、Coordinator 分解、@mention 路由、asyncio.gather 并发、Loop Guard、飞书管道(可选) | Celery DAG、task_events |
| **M4** 产物预览 | 6/2-5 | DiffCard 内联渲染、iframe PreviewCard、Pin 上下文、L2 摘要压缩 | L3/L4 记忆、deploy |
| **M5** 打磨 | 6/6-9 | 3min Demo 视频、UI 细节、端到端测试、文档终稿 | — |
| **M6** 提交 | 6/10 | 仓库整理、最终提交 | — |

---

## 七、当前代码改动清单

### 需要新增的文件

```
backend/app/infrastructure/llm/claude_cli_adapter.py   # CLI 子进程适配器
backend/app/application/services/coordinator_service.py # 协调者编排（分解+并发执行）
adapters/feishu_adapter.py                             # 飞书消息管道（可选）

frontend/src/components/agent/AgentCreateForm.tsx      # 卡片式 Agent 创建表单
frontend/src/components/agent/SkillsSelector.tsx       # Skills 多选组件
frontend/src/components/chat/GroupChatView.tsx         # 群聊视图（@mention + 多流）
frontend/src/components/chat/TaskPlanCard.tsx          # 协调者任务分解卡片
frontend/src/components/chat/DiffCard.tsx              # Diff 预览卡片 (M4)
frontend/src/components/chat/PreviewCard.tsx           # iframe 预览卡片 (M4)

tests/test_claude_cli_adapter.py
tests/test_coordinator_service.py
tests/test_loop_guard.py
```

### 需要修改的文件

```
backend/app/infrastructure/llm/factory.py
  → 增加 claude_cli 分支，从 Agent 配置构建 ClaudeCLIAdapter

backend/app/application/services/chat_service.py
  → _resolve_target_agent() 增加群聊 @mention 解析逻辑
  → send_and_stream() 增加 dispatch_mode=auto 的意图检测
  → 私有方法改为调用 CoordinatorService（群聊场景）

backend/app/domain/task_engine/harness.py
  → 增加 asyncio.gather 并发执行逻辑（替代 Celery Canvas）
  → 增加 LoopGuard

backend/app/api/ws/chat.py
  → 按 session 类型选择 SDK 或 CLI adapter

frontend/src/components/chat/ChatView.tsx
  → 增加群聊模式（多流显示、@mention 输入提示）
  → 增加 TaskPlanCard 渲染

frontend/src/stores/chatStore.ts
  → 增加多流消息处理
  → 增加 task_plan / tool_call 事件渲染
```

### 可以删除/归档的文件

```
backend/app/domain/events/          # 事件溯源相关 → 简化
backend/app/infrastructure/queue/   # Celery 相关 → 归档
spec/data-model_数据模型.md        # 更新为 6 表版本
```

---

## 八、FAQ：五个细节问题解答

### Q1: 群聊记忆系统和子进程记忆不会冲突吗？

**不会。** 分工边界明确：

- **Claude Code CLI 内部**：自己维护 messages[] 对话数组，从 JSONL session 文件读写。AgentHub **不干预**。
- **AgentHub L1**：维护 Redis 滑动窗口（最近 20 条群聊消息），用于 SDK 模式注入和上下文展示。**不在 CLI 模式注入**。
- **AgentHub L2**：维护 PG 摘要（跨会话压缩）。CLI 模式下，**仅在 session 首次创建时写入 CLAUDE.md**，之后不再注入。

两者通过**文件系统**交换信息，互不覆盖。

### Q2: 同一台电脑可以实现 Claude Code 不同 API 设置吗？

**可以。** 每个 CLI 子进程是独立进程，有独立的：
- 环境变量（`ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`）
- 工作目录（`/tmp/agenthub/sessions/{agent_id}/`）
- CLAUDE.md 文件（含 system prompt 和上下文）
- `.claude/skills/` 目录（含选中的 skill 文件）

不同 Agent 的子进程之间完全隔离，互不影响。

### Q3: Coordinator 分解是每个群聊开个 Agent 吗？

**是的。** 创建群组时，`GroupService.create()` 自动创建一个 `is_system=True` 的 Coordinator Agent。它：

- 不常驻运行，按需调用（只在用户触发任务分解时 spawn）
- 在群组成员列表中显示为蓝色系统标识
- 使用 SDK 模式（轻量，不需要完整 CLI 工具生态）
- 群组删除时级联删除

### Q4: 比赛 Demo 下最好最简方案？

见第六章里程碑计划。核心原则：
- **保留**：自建 Web 前端、Coordinator 分解、4 层记忆（L1-L2）、Task FSM
- **砍掉**：Celery DAG、事件溯源（task_events 表）、Repository 接口层、pgvector、部署
- **新增**：CLI 子进程模式、Loop Guard、流式消息缓冲、飞书管道（可选）

### Q5: IM 可以套 CLI 系统再自建 Web 前端吗？

**可以。** 飞书 Bot 做消息管道（推送和接收），Web 前端做富展示。飞书收简单通知 + "查看详情"链接，浏览器看完整聊天 + Diff + Preview 卡片。两者共享同一个 ChatService，通过 `source` 字段区分消息来源。

---

> **版本**: v3.0 | **日期**: 2026-05-23
> **变更**: 基于社区调研重写，SDK+CLI 双模式，asyncio.gather 替代 Celery，6 表精简，飞书管道可选，完整流程 walkthrough
