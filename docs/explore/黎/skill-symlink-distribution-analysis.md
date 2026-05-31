# Skill 跨 Agent 分发：cc-switch symlink 方案分析与对比

> 灵感来源：[farion1231/cc-switch](https://github.com/farion1231/cc-switch) — MIT 开源

## 一、cc-switch 怎么做

### 核心设计：SSOT + symlink

```
~/.cc-switch/skills/              ← SSOT（Single Source of Truth）
  ├── frontend-design/
  │   ├── SKILL.md
  │   └── scripts/
  ├── code-review/
  │   └── SKILL.md
  └── ...

~/.claude/skills/                 ← Claude Code 读取的位置
  ├── frontend-design/  → symlink → ~/.cc-switch/skills/frontend-design/
  └── code-review/      → symlink → ~/.cc-switch/skills/code-review/

~/.codex/skills/                  ← Codex 读取的位置
  ├── frontend-design/  → symlink → ~/.cc-switch/skills/frontend-design/
  └── code-review/      → symlink → ~/.cc-switch/skills/code-review/

~/.gemini/skills/                 ← Gemini CLI 读取的位置
  ├── frontend-design/  → symlink → ...
  └── code-review/      → symlink → ...
```

**一次安装，所有 CLI 工具自动可见。** 不需要复制文件，不占额外磁盘。

### 三种同步模式

| 模式 | 行为 |
|------|------|
| **Auto**（默认） | 优先 symlink，失败回退 copy |
| **Symlink** | 仅 symlink，不支持则报错 |
| **Copy** | 纯文件复制，适合跨文件系统 |

### 平台适配

- **Unix**: `std::os::unix::fs::symlink(src, dst)`
- **Windows**: `std::os::windows::fs::symlink_dir(src, dst)` — 需要开发者模式或管理员权限

### 安装流程

```
用户浏览 GitHub 仓库 → 选 skill → 一键安装
  ↓
下载 zip → 解压到 temp
  ↓
写入 SSOT: ~/.cc-switch/skills/{name}/
  ↓
sync_to_app_dir(): 对每个启用的 CLI app
  ├── 检查是否已有 symlink → 跳过
  ├── 尝试 symlink SSOT → app skills dir
  └── 失败则 copy
  ↓
记录到 SQLite（skill + app 绑定关系）
```

### 卸载

```
删除前自动备份 → ~/.cc-switch/skill-backups/（保留 20 份）
遍历所有 app → 删除对应 symlink
删除 SSOT 源目录
```

### 支持的 CLI 工具路径

| CLI | Skills 目录 |
|-----|------------|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.codex/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| OpenClaw | `~/.openclaw/skills/` |

---

## 二、AgentHub 当前方案

### 架构

```
.marketplace (skillsmp.com)
  ↓ search/install API
AgentHub Backend (Docker)
  ↓ GitHub Contents API 递归拉取
/ skills /                      ← Docker volume 挂载 .agenthub/skills/
  ├── xhs-interact/
  │   └── SKILL.md
  ├── html-ppt-xhs-post/
  │   └── SKILL.md
  └── dbs-xhs-title/
      └── SKILL.md
```

### 当前流程

1. 用户在 Web UI 搜索/安装 skill
2. 后端从 GitHub Contents API 递归拉取到 `.agenthub/skills/{name}/`
3. Docker volume 挂载：`.agenthub/skills/` → 容器内 `/skills/`
4. `_load_skill_content()` 读取 SKILL.md → 拼接到 agent system prompt
5. Agent 通过 Claude CLI 执行时，**CLI 自己读取 `~/.claude/skills/` 或项目 `.claude/skills/`**

### 关键问题

**技能文件只在 Docker 容器内，CLI Agent 在宿主机执行时看不到。**

```
用户浏览器 → AgentHub Web → Backend (Docker)
                               ↓ 构造 prompt 时注入 skill 内容
                               ↓ 调用 Claude CLI (宿主机)
                               ↓ CLI 读 ~/.claude/skills/ → 空的！没有 skill 文件
```

---

## 三、对比

| 维度 | cc-switch | AgentHub 当前 |
|------|----------|-------------|
| **存储位置** | `~/.cc-switch/skills/`（宿主机） | `.agenthub/skills/`（Docker volume） |
| **分发方式** | symlink 到每个 CLI app 目录 | 仅 Docker 容器内可读 |
| **CLI 可见性** | 所有 CLI 工具直接可见 | CLI 工具看不到（在容器里） |
| **多 Agent** | 同一份 skill 对所有 app 生效 | 靠 `skills: string[]` 字段按 Agent 分配 |
| **安装来源** | GitHub repo / ZIP | skillsmp.com → GitHub Contents API |
| **备份** | 自动备份，保留 20 份 | 无 |
| **跨平台** | Windows/macOS/Linux | Docker 内 Linux，宿主机无关 |
| **权限控制** | 无（所有 app 可见全部 skill） | 按 Agent 粒度（每个 Agent 独立 skill 列表） |
| **Web UI** | 桌面应用（Tauri） | Web 界面 |

---

## 四、AgentHub 可以借鉴的点

### 1. Symlink 分发到宿主机（核心差距）

AgentHub 的 CLI Agent（claude_code / pi_agent）运行在宿主机，但 skill 文件在 Docker 容器里。解决思路：

**方案 A：安装时将 skill 写到宿主机**
```
用户点击安装
  ↓
后端下载 skill 文件
  ↓
写到宿主机路径: {project}/.agenthub/skills/{name}/
  ↓
symlink 到 ~/.claude/skills/{name}/  （可选，对 CLI 模式必须）
  ↓
同时保留 Docker volume 挂载（Web 端 skill 列表查询用）
```

**方案 B：AgentHub 容器挂载宿主机 `.claude/skills/`**
```
docker-compose.yml:
  volumes:
    - ~/.claude/skills:/skills          # 直接挂载 Claude skills 目录
    - ../.agenthub/skills:/skills       # 或双挂载
```
问题：会污染 Claude Code 自身的 skill 管理。

### 2. Per-Agent 开关（vs 全量生效）

cc-switch 是"安装 = 所有 app 可见"，AgentHub 是"选中的 Agent 才加载"。

AgentHub 的粒度更细，但缺少**安装后自动对 CLI 可见**这一步。可以结合：

```
安装 skill → SSOT 入库
  ↓
用户分配给 Agent → Agent 启动时 symlink 到对应 CLI 目录
  ↓
Agent 销毁时移除 symlink（保留 SSOT）
```

### 3. 备份机制

cc-switch 的卸载前自动备份（保留 20 份）是很好的实践。AgentHub 可以做：
- 安装前 snapshot 当前 `.agenthub/skills/` 状态
- 提供回滚能力

### 4. Auto 模式（symlink 优先 + copy 兜底）

Windows 上 symlink 需要管理员权限，cc-switch 的 Auto 模式自动降级为 copy。AgentHub 跨平台部署（开发者在 Windows/macOS/Linux）时需要考虑。

---

## 五、建议的 AgentHub 改进路线

### 短期（当前分支可做）

1. **安装时同时写到宿主机路径**：`.agenthub/skills/{name}/` 已经挂载到容器，但容器内的文件实际就在宿主机这个目录。确认宿主机的 CLI 工具能读到这些文件。

2. **环境变量/配置指向**：在 Agent 配置中加入 `SKILLS_DIR` 或利用 Claude Code 的 `--skills-dir` 参数指向 `.agenthub/skills/`。

### 中期（下个迭代）

3. **Symlink 管理器**：安装 skill 时自动 symlink 到 `~/.claude/skills/{name}/`，卸载时清理。Windows 上用 junction 或 copy 降级。

4. **Per-Agent 可见性控制**：Agent 启动时只 symlink 分配给它的 skill，销毁时清理。

### 长期

5. **多 CLI 支持**：当接入 Codex/Gemini 等其他 CLI 时，symlink 到各自的 skills 目录。
