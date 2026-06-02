# Agent 工作空间完整方案（通用设计，适用所有 Agent 类型）

## 总览架构

```
┌─ 用户浏览器 ──────────────────────────────────────────────┐
│  Web UI (React)                                            │
│  - 选择 workspace 目录                                      │
│  - 聊天 + 文件 diff 审核                                    │
│  - Agent 模板管理                                           │
└──────────┬─────────────────────────────────────────────────┘
           │ HTTP + WebSocket
┌──────────┴──────────────┐    ┌─ 宿主机 ──────────────────────┐
│ AgentHub Backend (Docker)│    │ CLI Runner (Python 常驻进程)   │
│                          │←WS→│                               │
│ - API 代理               │    │ - 接收执行指令（与 Agent 无关）│
│ - 消息/会话持久化          │    │ - 启动子进程 (cwd 约束)       │
│ - WebSocket 推送          │    │ - 管理 Git 分支                │
│ - Git 操作编排            │    │ - 返回 diff 给 Backend         │
└──────────────────────────┘    └──────────┬────────────────────┘
                                           │ cwd = workspace
                                    ┌──────┴──────────┐
                                    │ D:\projects\blog │
                                    │  ├── src/        │
                                    │  ├── .git/       │
                                    │  └── CLAUDE.md   │
                                    └─────────────────┘
```

**核心原则**：
- Backend (Docker) 管逻辑 — 消息路由、权限、编排，**不关心是哪种 Agent**
- CLI Runner (宿主机) 管执行 — 起子进程、文件操作、git，**对所有 CLI Agent 通用**
- 两者通过 WebSocket 双向通信
- **workspace 是 Session 级概念，与 Agent 类型无关**

## 适用 Agent 类型

| Agent 类型 | workspace 行为 | CLI Runner 做的事 |
|-----------|---------------|------------------|
| **claude_code** | cwd=workspace, `claude` 子进程 | `create_subprocess_exec("claude", cwd=workspace)` |
| **pi_agent** | cwd=workspace, `pi` 子进程 | `create_subprocess_exec("pi", cwd=workspace)` |
| **mock** | 无实际执行，但 UI 仍可展示 workspace | 不经过 CLI Runner，Backend 直接 mock 回复 |
| **codex (未来)** | cwd=workspace, `codex` 子进程 | `create_subprocess_exec("codex", cwd=workspace)` |
| **gemini (未来)** | cwd=workspace, `gemini` 子进程 | `create_subprocess_exec("gemini", cwd=workspace)` |

CLI Runner 不关心具体是哪个 CLI — 它只收到一个执行指令：
```json
{
  "binary": "claude",        // 或 "pi", "codex", "gemini"
  "args": ["--print", ...],  // 各 CLI 自己的参数
  "cwd": "D:\\projects\\blog",
  "prompt": "...",
  "env": {...}
}
```

Backend（`factory.py`）根据 Agent 类型拼好 `binary` 和 `args`，Runner 只管执行。

---

## 一、CLI Runner

### 1.1 部署方式

CLI Runner 是宿主机上运行的独立 Python 进程，随 AgentHub 启动：

```
# 宿主机终端
cd D:\AgentHub\repo
python cli_runner/main.py
```

### 1.2 通信协议

CLI Runner 通过 WebSocket 连接到 AgentHub Backend：

```
Runner → Backend:  {"type": "hello", "runner_id": "...", "hostname": "..."}
Backend → Runner:  {"type": "ack"}

Backend → Runner:  {"type": "exec", "request_id": "...", "session_id": "...",
                     "cli": "claude", "workspace": "D:\\projects\\blog",
                     "system_prompt": "...", "prompt": "...",
                     "agent_id": "...", "env": {...}}

Runner → Backend:  {"type": "stream", "request_id": "...", "event": {...}}
Runner → Backend:  {"type": "done", "request_id": "...", "diff": {...}}
Runner → Backend:  {"type": "error", "request_id": "...", "error": "..."}
```

### 1.3 子进程启动（通用）

```python
# cli_runner/executor.py
async def execute(request):
    workspace = Path(request["cwd"])
    binary = request["binary"]     # "claude" | "pi" | "codex" | ...
    args = request["args"]         # 各 CLI 自己的参数
    
    # 校验 workspace 存在
    if not workspace.exists():
        return {"type": "error", "error": f"目录不存在: {workspace}"}
    
    # 通用子进程启动 — binary 和 args 由 Backend 拼好
    proc = await asyncio.create_subprocess_exec(
        binary, *args,
        cwd=str(workspace),           # ← 对所有 CLI 有效
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **request.get("env", {})},
    )
    
    # 写入 prompt → 逐行读 stdout → 转发 Backend
    proc.stdin.write(request["prompt"].encode())
    proc.stdin.close()
    
    async for line in proc.stdout:
        event = json.loads(line)
        await ws.send({"type": "stream", "request_id": request["id"], 
                        "event": event})
    
    # 完成后收集 diff（所有 CLI Agent 都一样）
    diff = collect_git_diff(workspace)
    await ws.send({"type": "done", "request_id": request["id"], 
                    "diff": diff})
```

**Binary/Args 在哪拼？** — 在 Backend 的 `factory.py` 里，每个 Agent 类型生成自己的 `binary` 和 `args`：

```python
# Claude Code:  factory.py → ClaudeCodeRuntime._build_cmd()
binary = "claude"
args = ["--print", "--session-id", session_key, ...]

# Pi Agent:     factory.py → PiAgentRuntime._build_cmd()
binary = "pi"
args = ["--mode", "rpc", "--session", session_file, ...]

# Codex (未来): factory.py → CodexRuntime._build_cmd()
binary = "codex"
args = ["--session", session_key, ...]
```

Runner 完全不关心 `binary` 是什么 — 它是纯透传执行器。

---

## 二、Git 协作模式

### 2.1 基本流程

```
1. Agent 收到任务
2. CLI Runner 在 workspace 下创建临时分支
3. Agent 在分支上自由修改
4. 完成后 Runner 返回:
   - 改动了哪些文件
   - 完整 diff
   - commit message（Agent 生成）
5. 用户在前端审核
6. 用户决定: 合并 / 撤回 / 手动修改后再合并
```

### 2.2 分支命名规则

```
agent/{session_id}/{agent_name}/{timestamp}
例: agent/sess-abc123/engineer/20260528-143022
```

每个 Agent 在自己的分支上工作，互不影响。

### 2.3 用户审核流程

```
Agent 完成后:
┌─ 聊天消息 ─────────────────────────────────────┐
│ 🤖 工程师  刚刚修改了项目                        │
│                                                │
│ 📝 提交信息: 重构 utils/date.ts，提取时间格式化   │
│ 📁 修改了 2 个文件:                              │
│  ✏️ src/utils/date.ts    (+45 -12)             │
│  ✏️ src/utils/__tests__/date.test.ts (+30)     │
│                                                │
│ [查看完整 diff]  [合并改动]  [撤回改动]           │
└────────────────────────────────────────────────┘

点击 [查看完整 diff]:
┌─ Diff 查看器 ──────────────────────────────────┐
│ src/utils/date.ts                              │
│                                                │
│ + export function formatDate(d: Date): string {│
│ +   return d.toISOString().slice(0, 10)        │
│ + }                                            │
│                                                │
│ - function fmt(d: Date) {                      │
│ -   return d.toLocaleDateString()              │
│ - }                                            │
│                                                │
│                        [合并]  [关闭]            │
└────────────────────────────────────────────────┘
```

### 2.4 群聊场景：两个 Agent 改同一文件

```
用户: "@工程师 重构 utils, @代码评审 检查类型安全"
  ↓
协调者分配:
  1. 工程师先执行 → agent 分支 A → 改 src/utils/date.ts → 提交 → 等待审核
  2. 代码评审等工程师完成 → agent 分支 B (基于 A 的改动)
     → 审查类型 → 如果有问题直接在 B 上改 → 提交 → 等待审核
  
用户看到:
  [工程师] 重构 utils (已完成，等待审核) [查看] [合并]
  [代码评审] 检查类型安全 (已完成，等待审核) [查看] [合并]
  
用户:
  1. 先审核工程师的改动 → 合并
  2. 再审核代码评审的改动 → 合并（此时 B 分支基于已合并的 A）
```

**关键**: 后执行的 Agent 的临时分支**基于前一个 Agent 的分支最新状态**，而不是原始 main。这样不会产生冲突。

### 2.5 回滚

```
用户点击 [撤回改动]:
  → git checkout main (恢复 workspace 到 Agent 改动前的状态)
  → 删除临时分支 agent/{session_id}/{agent_name}/{timestamp}
```

### 2.6 Agent 级别回退

如果用户已经合并了 Agent A 的改动，又合并了 Agent B 的改动，然后想回退 B：

```
git revert <B 的 merge commit>
```

AgentHub 记录每个 merge commit，支持一键 revert。

---

## 三、数据模型

### 3.1 新增/修改的表

**Session 表新增**：
```sql
ALTER TABLE sessions ADD COLUMN workspace_path TEXT;
-- 例: "D:\\projects\\blog" 或 "/home/user/projects/blog"
```

**新增 AgentChange 表**：
```sql
CREATE TABLE agent_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    branch_name TEXT NOT NULL,          -- agent/sess-abc/engineer/20260528
    commit_message TEXT,
    files_changed JSONB DEFAULT '[]',  -- [{"path": "...", "added": 45, "removed": 12}]
    diff TEXT,                         -- 完整 unified diff
    status TEXT DEFAULT 'pending',     -- pending | merged | reverted
    merge_commit TEXT,                 -- merge 后的 commit SHA
    base_commit TEXT,                  -- Agent 开始前的 HEAD SHA
    created_at TIMESTAMP DEFAULT NOW(),
    merged_at TIMESTAMP,
    merged_by TEXT                     -- 谁点的合并（用户或 Agent）
);
```

### 3.2 CLI Runner 执行指令

```python
# Backend → CLI Runner 的消息格式
class ExecRequest:
    request_id: str
    session_id: str
    agent_id: str
    agent_name: str
    cli: str                         # "claude" | "pi"
    workspace: str                   # 绝对路径
    system_prompt: str
    prompt: str                     # 用户消息文本
    env: dict                       # 环境变量 (ANTHROPIC_BASE_URL 等)
    base_branch: str | None         # 基于哪个分支（群聊串行时用）
```

---

## 四、前端完整流程

### 4.1 创建私聊会话

```
Step 1: 选择 Agent
  → 从 Agent 列表选中

Step 2: 选择工作空间
  ┌─────────────────────────────────┐
  │ 工作空间（Agent 将在此目录工作）   │
  │                                 │
  │ ┌─────────────────────────────┐ │
  │ │ D:\projects\blog            │ │
  │ └─────────────────────────────┘ │
  │ [浏览文件夹...]                  │
  │                                 │
  │ 📂 最近使用:                     │
  │  · D:\projects\design-system    │
  │  · D:\AgentHub\repo             │
  │                                 │
  │ ⚠️ Agent 只能在以上目录及其       │
  │    子目录中读写文件               │
  │                                 │
  │          [开始对话]              │
  └─────────────────────────────────┘
```

### 4.2 聊天界面

```
┌─ header ────────────────────────────────────────────┐
│ 🤖 工程师  AI · 📁 blog · 🌿 main                      │
│   工作空间: D:\projects\blog                           │
└──────────────────────────────────────────────────────┘
┌─ 消息区 ────────────────────────────────────────────┐
│ ...                                                  │
│                                                      │
│ ┌─ Agent 改动通知 ──────────────────────────────┐   │
│ │ 工程师 修改了 2 个文件                         │   │
│ │ src/utils/date.ts       (+45 -12)             │   │
│ │ src/utils/__tests__/date.test.ts (+30)        │   │
│ │ [查看 diff] [合并改动] [撤回]                   │   │
│ └──────────────────────────────────────────────┘   │
│                                                      │
│ ┌─ Git Log ────────────────────────────────────┐   │
│ │ ✅ Agent 工程师 合并 (5 分钟前)                │   │
│ │ ✅ Agent 代码评审 合并 (10 分钟前)             │   │
│ │ ↩️ Agent 测试 已撤回 (15 分钟前)              │   │
│ └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### 4.3 群聊创建

```
Step 1: 选择群成员
Step 2: 设置 dispatch_mode (AT_ROUTING / DISCUSSION)
Step 3: 选择共享工作空间

  ┌─────────────────────────────────┐
  │ 群聊工作空间（所有成员共享）       │
  │                                 │
  │ 📁 D:\projects\design-system    │
  │ [浏览文件夹...]                  │
  │                                 │
  │ ⚠️ 群内所有 Agent 都将在这个      │
  │    目录下协作                    │
  └─────────────────────────────────┘
```

### 4.4 Agent 模板包含 workspace hint

```
创建模板 "React 开发者":
  名称: React 开发者
  System Prompt: 你是一个 React 专家...
  Skills: [react-best-practices, typescript]
  工作空间提示: 需要 React 项目目录 (含 package.json)
  
导入模板到另一台设备:
  → 提示: 请为本模板选择本地 React 项目目录
  → 用户选: /Users/name/work/my-app
  → 完成
```

### 4.5 右侧文件面板（后续 Phase）

```
┌─ 文件 ────────────────────────┐
│ 📁 blog/                      │
│  ├── 📁 src/                  │
│  │   ├── 📄 index.ts       ✏️ │
│  │   └── 📁 utils/            │
│  │       └── 📄 date.ts    ✏️ │
│  ├── 📄 CLAUDE.md             │
│  ├── 📄 package.json          │
│  └── 📄 .gitignore            │
│                               │
│ 🌿 agent/engineer/20260528    │
│    [查看 diff] [合并] [撤回]   │
└───────────────────────────────┘
```

---

## 五、安全约束

### 5.1 工作空间校验

```python
# cli_runner/validator.py
def validate_workspace(path: str, allowed_roots: list[str] | None = None) -> bool:
    p = Path(path).resolve()
    
    # 1. 必须存在且是目录
    if not p.exists() or not p.is_dir():
        return False
    
    # 2. 必须是绝对路径
    if not p.is_absolute():
        return False
    
    # 3. 可选: 限制在允许的根目录下
    if allowed_roots:
        in_allowed = any(
            str(p).startswith(str(Path(root).resolve())) 
            for root in allowed_roots
        )
        if not in_allowed:
            return False
    
    return True
```

### 5.2 工作空间白名单（配置项）

```json
// .agenthub/config.json
{
  "workspace": {
    "allowed_roots": ["D:\\projects", "D:\\AgentHub"],
    "require_git": true,
    "auto_create": false
  }
}
```

- `allowed_roots`: 只允许在这些目录下选择 workspace
- `require_git`: workspace 必须是 git 仓库（启用 git 分支协作）
- `auto_create`: 是否允许用户输入不存在的路径并自动创建

### 5.3 每次启动 CLI 前检查

```
1. workspace 路径存在 ✓
2. workspace 在允许的根目录内 ✓
3. workspace 是 git 仓库 ✓ (如果 require_git=true)
4. 无其他 Agent 正在修改同一文件 ✓ (可选文件锁)
```

---

## 六、群聊执行时序

### 6.1 V1 串行（当前实现）

```
用户: "@工程师 重构 utils, @代码评审 检查类型安全"
  ↓
1. Backend 解析 mentions → [工程师, 代码评审]
2. Backend → CLI Runner: exec(工程师, workspace, prompt="重构 utils")
3. CLI Runner:
   a. git checkout -b agent/sess-abc/engineer/20260528
   b. claude --cwd workspace "重构 utils"
   c. git add -A && git commit -m "..."
   d. 返回 diff
4. Backend 保存 AgentChange (status=pending)
5. Backend → CLI Runner: exec(代码评审, workspace, prompt="检查类型安全",
                              base_branch="agent/sess-abc/engineer/20260528")
6. CLI Runner:
   a. git checkout agent/sess-abc/engineer/20260528  ← 基于工程师的改动
   b. git checkout -b agent/sess-abc/review/20260528
   c. claude --cwd workspace "检查类型安全"
   d. git add -A && git commit -m "..."
   e. 返回 diff
7. Backend 保存 AgentChange (status=pending)
8. 前端显示两个待审核改动
```

### 6.2 讨论模式（DISCUSSION）

```
用户发消息（无 @）→ dispatch_mode == DISCUSSION
  ↓
讨论协调者分析消息 → 判断需要哪些 Agent 参与
  ↓
为每个 Agent 创建子任务 → 串行执行（同上）
  ↓
每个 Agent 改动独立提交、独立审核
```

### 6.3 用户合并顺序

```
情况 A: 两个 Agent 改不同的文件 → 用户可以先合并任一，无冲突
情况 B: 两个 Agent 改同一文件不同位置 → git 自动合并
情况 C: 两个 Agent 改同一文件同一位置 → 合并时冲突
  → AgentHub 检测冲突 → 提示用户手动解决
  → 或者启动第三个 Agent 专门解决冲突
```

---

## 七、实施路线

| Phase | 内容 | 依赖 |
|-------|------|------|
| **P0** | CLI Runner 单独进程 + Backend WS 通信 + cwd 约束 | 需要 Runner 能调 claude |
| **P1** | Session 加 workspace_path + 前端选目录 + chat header 显示 | P0 |
| **P2** | Git 分支隔离 + AgentChange 表 + 前端 diff 查看器 | P1 |
| **P3** | 用户审核工作流（查看→合并/撤回）+ 回滚 | P2 |
| **P4** | 群聊串行基于前一个分支 + 冲突检测 | P2 |
| **P5** | 文件面板 + workspace 白名单 + 跨设备模板映射 | P1 |

### P0 最小可行版本

改 3 个文件就能跑起来：

```
1. cli_runner/main.py         ← 新建，CLI Runner 常驻进程
2. claude_code_runtime.py     ← 改为连 Runner WS 而非直接起子进程
3. ChatView.tsx               ← 创建会话时让用户选目录，传给 Backend
```
