# Agent 工作空间设计方案

## 0. 前置：CLI Runner 放在哪

```
┌─ Docker ─────────────────────────┐     ┌─ 宿主机 (Windows) ────┐
│ AgentHub Backend (FastAPI)        │     │ CLI Runner (后台常驻)    │
│ - API 代理                        │←WS→│ - 管理 claude 子进程     │
│ - 消息持久化                       │     │ - cwd 约束               │
│ - WebSocket 推送                  │     │ - 文件系统隔离           │
└──────────────────────────────────┘     └────────────────────────┘
```

CLI Runner 在宿主机运行，Backend 在 Docker。Runner 收到 Backend 的 WS 消息后，启动 `claude` 子进程并指定 `cwd`。这样 claude 直接读写 `D:\my-project\`，不需要 Docker 挂载。

---

## 1. 群组 vs 个人工作空间

**结论：工作空间绑定在会话（Session）上，不绑定在 Agent 上。**

```
Session（私聊）
  ├── workspace: D:\projects\blog
  ├── agent: 工程师
  └── 只有这个 Agent 能操作这个目录

Session（群聊）
  ├── workspace: D:\projects\design-system
  ├── agents: [协调者, 工程师, 代码评审]
  └── 群内所有 Agent 共享工作空间，协作同一个项目
```

**规则**：
- 私聊 Session → workspace 是个人选的，仅此对话可见
- 群聊 Session → workspace 是群共享的，创建群时指定
- 同一个 Agent 在不同 Session 可以有不同 workspace
- Agent 模板不携带 workspace 路径

---

## 2. 如何真正约束 Agent 的文件访问

### 2.1 核心机制：subprocess cwd

```python
# claude_code_runtime.py
proc = await asyncio.create_subprocess_exec(
    "claude", "--print", "--session-id", session_key,
    cwd=str(workspace_path),          # ← 这一行约束了 claude 的根目录
    stdin=PIPE, stdout=PIPE, stderr=PIPE,
)
```

`cwd` 参数让子进程的当前工作目录锁定在指定路径。`claude` CLI 默认在 `cwd` 下操作文件，所有相对路径都以此为根。

### 2.2 额外加固（可选，按优先级）

| 层级 | 方式 | 说明 |
|------|------|------|
| **L1 进程级** | `cwd` 参数 | 最基础，所有 CLI 都遵守 |
| **L2 权限模式** | `--permission-mode acceptEdits` | Claude CLI 默认就开，允许写文件 |
| **L3 容器级** | Docker volume 只挂载 workspace | 如果用 Docker 跑 CLI，只挂这个目录 |
| **L4 系统级** | Windows 用户权限 | 给 CLI Runner 单独开低权限用户 |

### 2.3 前端安全提示

创建会话选择 workspace 时，前端显示：
> "Agent 将只能访问 `D:\projects\blog\` 目录及其子目录"

创建后不可修改 workspace（防止 hijack）。

---

## 3. 前端如何显示

### 3.1 创建会话时选择 workspace

```
┌─ 创建会话 ──────────────────────┐
│ Agent: 工程师                     │
│                                   │
│ 工作空间:                         │
│ ┌─────────────────────────────┐  │
│ │ D:\projects\blog            │  │
│ └─────────────────────────────┘  │
│ [浏览文件夹]  [最近使用 ▾]        │
│                                   │
│ 上次用过:                         │
│ · D:\projects\design-system       │
│ · D:\AgentHub\repo                │
│                                   │
│          [取消]  [开始对话]        │
└───────────────────────────────────┘
```

### 3.2 聊天界面 header

```
┌─ 聊天 header ──────────────────────────────────────┐
│ 🤖 工程师  AI  ·  📁 blog  ·  工作目录: projects\blog │
└─────────────────────────────────────────────────────┘
```

### 3.3 Agent 详情/Settings 标签

```
工作空间:  D:\projects\blog    [更换]
最近会话:
  · D:\projects\blog (5/28)
  · D:\projects\api (5/27)
```

### 3.4 右侧面板（可选，后续 Phase）

显示当前 workspace 的文件树，让用户看到 Agent 创建/修改了哪些文件：

```
📁 blog/
  ├── src/
  │   ├── index.ts
  │   └── posts/
  └── CLAUDE.md
```

---

## 4. 跨设备工作目录

### 4.1 存储格式

**Session 表新增字段**：

```sql
ALTER TABLE sessions ADD COLUMN workspace_path TEXT;
```

存储的是**用户输入的原生路径**，不做转换：
- Windows: `D:\projects\blog`
- macOS: `/Users/name/projects/blog`
- Linux: `/home/name/projects/blog`

### 4.2 模板如何跨设备

Agent 模板**不携带 workspace 路径**。路径是每个设备用户自己选的。

模板只需说明项目类型：
```json
{
  "name": "React 项目 Agent",
  "system_prompt": "...",
  "skills": ["react-best-practices"],
  "workspace_hint": "需要 React 项目目录"
}
```

在不同设备上导入模板后，用户自己选本地路径映射。

### 4.3 路径校验

后端在启动 CLI 前校验：
```python
def validate_workspace(path: str) -> bool:
    p = Path(path)
    return p.exists() and p.is_dir() and p.is_absolute()
```

不存在 → 前端提示 "目录不存在，是否创建？"

### 4.4 跨设备同步（可选后续）

如果以后要云同步 workspace，存路径映射配置：
```json
// 设备 A
{ "workspace_name": "blog-project", "path": "D:\\projects\\blog" }

// 设备 B  
{ "workspace_name": "blog-project", "path": "/Users/name/work/blog" }
```

按名称匹配而非路径匹配。但 MVP 不需要。

---

## 5. 子 Agent 搜索

### 5.1 搜索场景

```
用户: "在这个项目里找到所有用了 express 的路由文件"
  →
AgentHub 启动子 Agent:
  claude --cwd D:\projects\blog
  prompt: "用 grep 或 code search 找到所有用到 express 路由的文件"
  →
子 Agent 执行搜索 → 返回结果 → 主 Agent 汇总回答
```

### 5.2 搜索方式

| 方式 | 说明 |
|------|------|
| **claude 自带搜索** | `claude` CLI 有内置的 grep/file search 工具，自动在 cwd 下搜索 |
| **AgentHub Search API** | 后端提供 `/api/workspace/search?path=...&q=...` 供 Agent 调用 |
| **sub-agent 搜索** | 主 Agent 拆任务给子 Agent，子 Agent 各自搜索不同目录/关键词 |

### 5.3 子 Agent 搜索流程

```
主 Agent 收到 "在项目中找所有 TODO 注释"
  ↓
拆分任务:
  sub-agent-1: 搜索 src/ 下所有 .ts 文件中的 TODO
  sub-agent-2: 搜索 src/ 下所有 .tsx 文件中的 TODO
  ↓
每个 sub-agent: claude --cwd D:\projects\blog "grep TODO in *.ts"
  ↓
聚合结果 → 返回用户
```

子 Agent 的 `cwd` 继承父 Session 的 workspace，不需要再次设置。

---

## 实现优先级

| Phase | 内容 | 改动范围 |
|-------|------|---------|
| **P1 本迭代** | Session 加 workspace_path、前端选目录、CLI 传 cwd、chat header 显示 | Session 表 + CLI runtime + ChatView |
| **P2 下迭代** | 文件树面板、workspace 校验、最近使用列表 | 右侧面板 + 前端 |
| **P3 后续** | 子 Agent 搜索、跨设备映射 | 后端 + 前端 |
