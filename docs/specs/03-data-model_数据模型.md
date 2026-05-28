# AgentHub 数据模型

> 版本: v2.0 | 基于 PRD v1.0 §五 + 架构设计 v1.0
> ⚠️ v4 PRD 已将 12 表简化为 6 表（砍掉 agent_capabilities / task_events / task_artifacts / notifications / deploy_logs / users）。本文件尚未同步，实现以 v4 PRD 为准。
> 所有 SQL 以 Alembic migration 形式管理。

---

## 一、核心实体关系

```
User ──┬── Session (会话) ──── Message (消息)
       │       │                    │
       │       ├── GroupSession      ├── text
       │       └── PrivateSession     ├── diff
       │                             ├── preview_card
       │                             ├── task_plan
       │                             └── approval_request
       │
       ├── Agent ─── agent_capabilities
       │    │
       │    ├── channels[] (所属群组)
       │    ├── tasks[] (已分配任务)
       │    ├── activities (活动日志)
       │    └── memory_config
       │
       ├── Group (群组/频道) ─── Coordinator (协调者, 1:1)
       │    │
       │    ├── group_members (Agent 列表)
       │    └── sessions[] (群组内会话)
       │
       ├── Task (任务)
       │    ├── parent_task_id (从属关系)
       │    ├── subtasks[]
       │    └── task_events[] (事件日志)
       │
       └── Notification (收件箱)
            ├── category: approval/task/calendar
            └── is_read
```

---

## 二、表结构

### 2.1 users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    avatar TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 2.2 agents

```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    avatar TEXT NOT NULL,
    role TEXT NOT NULL,

    -- Agent 系统 + 底层模型 (两级选择)
    agent_system TEXT NOT NULL CHECK (agent_system IN ('claude', 'codex', 'trae')),
    provider TEXT NOT NULL,                  -- 实际 LLM 厂商: anthropic/openai/deepseek/zhipu/...
    model TEXT NOT NULL,                     -- 模型名: gpt-4o / deepseek-chat / glm-4 / ...
    base_url TEXT,                           -- 自定义 API 端点 (兼容任意 OpenAI 格式 API)
    api_key_encrypted TEXT NOT NULL,         -- AES-256-GCM 加密存储

    system_prompt TEXT,                      -- 自定义 system prompt
    capability_tags TEXT[] DEFAULT '{}',     -- ["react", "python", "css"]
    skills TEXT[] DEFAULT '{}',              -- 初始技能列表

    -- 系统维护字段
    status TEXT DEFAULT 'online',            -- online / offline / busy / error
    is_system BOOLEAN DEFAULT FALSE,         -- 协调者为 TRUE
    workload INT DEFAULT 0,                  -- 当前任务数
    settings JSONB DEFAULT '{}',             -- max_tokens, concurrency, temperature...
    memory_config JSONB DEFAULT '{}',        -- L1-L4 记忆参数

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ                   -- 软删除
);

CREATE INDEX idx_agents_system ON agents (agent_system);
CREATE INDEX idx_agents_status ON agents (status) WHERE deleted_at IS NULL;
```

### 2.3 agent_capabilities

```sql
CREATE TABLE agent_capabilities (
    id BIGSERIAL PRIMARY KEY,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,                       -- "react", "python"...
    UNIQUE (agent_id, tag)
);

CREATE INDEX idx_agent_cap_agent ON agent_capabilities (agent_id);
```

### 2.4 groups

```sql
CREATE TABLE groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    coordinator_config JSONB DEFAULT '{}',   -- 协调者模型/参数
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 2.5 group_members

```sql
CREATE TABLE group_members (
    id BIGSERIAL PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (group_id, agent_id)
);

CREATE INDEX idx_gm_group ON group_members (group_id);
CREATE INDEX idx_gm_agent ON group_members (agent_id);
```

### 2.6 sessions

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('group', 'private')),
    title TEXT NOT NULL DEFAULT '',
    group_id UUID REFERENCES groups(id),     -- type=group 时必填
    agent_id UUID REFERENCES agents(id),     -- type=private 时关联的 Agent
    long_term_context JSONB DEFAULT '{}',     -- Pin 消息 + 压缩摘要
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sessions_updated ON sessions (updated_at DESC);
```

### 2.7 messages

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    agent_name TEXT,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text' CHECK (content_type IN (
        'text', 'code_diff', 'preview_url', 'deploy_status',
        'task_plan', 'approval_request', 'file_attachment', 'doc_preview', 'error'
    )),
    mentions TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    reply_to UUID REFERENCES messages(id),
    status TEXT DEFAULT 'sent' CHECK (status IN ('sending', 'sent', 'streaming', 'done', 'error')),
    pinned BOOLEAN DEFAULT FALSE,
    idempotency_key TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_msg_session ON messages (session_id, created_at);
```

### 2.8 tasks

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'queued', 'running', 'awaiting_approval',
        'paused', 'completed', 'failed', 'cancelled'
    )),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    assignee_id UUID REFERENCES agents(id),
    assignee_type TEXT CHECK (assignee_type IN ('agent', 'group')),
    parent_task_id UUID REFERENCES tasks(id),
    session_id UUID REFERENCES sessions(id),  -- 来源会话
    source TEXT DEFAULT 'chat' CHECK (source IN ('chat', 'manual')),
    due_date TIMESTAMPTZ,
    tags TEXT[] DEFAULT '{}',
    -- 预算
    tokens_used BIGINT DEFAULT 0,
    budget_max_tokens BIGINT DEFAULT 100000,
    budget_max_steps INT DEFAULT 10,
    budget_max_duration_secs INT DEFAULT 600,
    steps INT DEFAULT 0,
    retry_count INT DEFAULT 0,
    gates_passed BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_tasks_status ON tasks (status, priority, created_at) WHERE status = 'queued';
CREATE INDEX idx_tasks_assignee ON tasks (assignee_id, status);
CREATE INDEX idx_tasks_parent ON tasks (parent_task_id);
CREATE INDEX idx_tasks_session ON tasks (session_id);
CREATE INDEX idx_tasks_due ON tasks (due_date) WHERE status NOT IN ('completed', 'cancelled');
```

### 2.9 task_events

```sql
CREATE TABLE task_events (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(id),
    event_type TEXT NOT NULL,               -- task_created / state_changed / step_started /
                                            -- step_completed / human_approved / human_rejected /
                                            -- task_failed / task_completed
    event_data JSONB NOT NULL,
    actor TEXT,                              -- agent_name / 'user' / 'system'
    causation_id BIGINT,
    idempotency_key TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_te_task ON task_events (task_id, id);
CREATE UNIQUE INDEX idx_te_idempotency ON task_events (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
```

### 2.10 task_artifacts

```sql
CREATE TABLE task_artifacts (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(id),
    step_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    input JSONB,
    output JSONB,
    error JSONB,
    tokens_used BIGINT DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ta_task ON task_artifacts (task_id, step_name);
```

### 2.11 notifications

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    type TEXT NOT NULL CHECK (type IN ('approval', 'task', 'system')),
    category TEXT DEFAULT 'all',
    title TEXT NOT NULL,
    content TEXT,
    action_url TEXT,
    metadata JSONB DEFAULT '{}',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_notif_user ON notifications (user_id, is_read, created_at DESC);
```

### 2.12 deploy_logs

```sql
CREATE TABLE deploy_logs (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID REFERENCES tasks(id),
    environment TEXT DEFAULT 'staging',
    status TEXT NOT NULL,
    deploy_url TEXT,
    error_log TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 三、Pydantic Schema

### 3.1 Agent 创建

```python
class CreateAgentRequest(BaseModel):
    agent_system: Literal["claude", "codex", "trae"]
    name: str = Field(min_length=1, max_length=50)
    avatar: str
    role: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1)        # anthropic / openai / deepseek / zhipu...
    model: str = Field(min_length=1)            # gpt-4o / deepseek-chat...
    api_key: str = Field(min_length=1)          # 明文传入，L3 加密后存储
    base_url: str | None = None                 # 自定义 API 端点
    skills: list[str] = []
    system_prompt: str | None = None
    capability_tags: list[str] = []
```

### 3.2 消息发送

```python
class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    content_type: str = "text"
    mentions: list[str] = []                    # @ 的 Agent name 列表
    reply_to: UUID | None = None
    dispatch_mode: Literal["auto", "direct"] = "auto"
    # auto: 系统判断 (@协调者→触发 / @Agent→路由 / 无@→LLM意图检测)
    # direct: 私聊固定使用
```

### 3.3 任务计划

```python
class SubTask(BaseModel):
    id: str
    description: str
    suggested_worker: str
    dependencies: list[str] = []
    validation_gate: str

class TaskPlan(BaseModel):
    plan_id: str
    tasks: list[SubTask]
    execution_strategy: Literal["parallel", "sequential", "mixed"] = "mixed"

# Coordinator Agent LLM 输出的完整决策
class CoordinatorDecision(BaseModel):
    action: Literal["decompose_and_dispatch", "handle_failure", "request_approval"]
    plan: TaskPlan | None = None
    task_id: str | None = None
    diagnosis: str | None = None
    suggestion: Literal["retry", "cancel", "escalate"] | None = None
```

---

## 四、API Key 加密存储

```python
from cryptography.fernet import Fernet
import os

# 密钥从环境变量注入，不写死在代码
FERNET_KEY = os.environ["AGENTHUB_ENCRYPTION_KEY"]

def encrypt_api_key(plain: str) -> str:
    return Fernet(FERNET_KEY).encrypt(plain.encode()).decode()

def decrypt_api_key(encrypted: str) -> str:
    return Fernet(FERNET_KEY).decrypt(encrypted.encode()).decode()
```

- API Key 输入后不可再查看明文，仅支持**重置**
- 需读取 key 时（传递给 Adapter），从 DB 取出后解密使用，用完即丢弃

---

## 五、Agent 活动日志（activities）

```python
# 存储在 agents.activities JSONB 列，或独立表
# 结构:
class AgentActivity(BaseModel):
    id: UUID
    agent_id: UUID
    action: str          # "task_started" | "task_completed" | "joined_group" | ...
    detail: str
    timestamp: datetime

# 获取: GET /api/agents/{id}/activities?page=1
```
