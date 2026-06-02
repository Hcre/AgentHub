# 部署架构反思：为什么 Docker Desktop 反复坏 + 新用户应该怎么部署

## 一、Docker Desktop 反复坏的原因

### 根因：Docker Desktop on WSL2 的五层依赖链

```
Windows 宿主机
  └─ WSL2 VM (轻量 Hyper-V)
       └─ docker-desktop 发行版
            └─ Docker Engine (dockerd)
                 └─ 容器
```

任何一层出问题，整个链断裂：

1. **WSL2 distro 磁盘损坏** — `fork/exec /usr/local/bin/dockerd: input/output error`。WSL2 虚拟磁盘文件 (`ext4.vhdx`) 在非正常关机/强制 kill 时会损坏
2. **com.docker.backend.exe 崩溃** — Docker Desktop 的后台代理进程，管端口转发。崩溃后 `docker ps` 返回 500
3. **WSL2 代理冲突** — `127.0.0.1:7897` (Clash) 代理没开，Docker Desktop 走系统代理导致拉不了镜像
4. **WSL2 与 Docker Desktop distro 竞态** — 我们反复 `wsl --unregister docker-desktop` + 删除 AppData → Docker Desktop 重新创建 distro → 慢 → 超时 → 用户重启 → 又损坏

### 我们做的加剧问题的操作

| 操作 | 后果 |
|------|------|
| `wsl --unregister docker-desktop` | nuke Docker 的核心 WSL 发行版 |
| `rm -rf %APPDATA%\Docker` | nuke Docker 的所有配置+缓存 |
| `wsl --shutdown` | 强制杀 WSL VM，可能导致磁盘损坏 |
| 反复重装 Docker Desktop | 每次重装 WSL distro 都要重新创建，网络慢则超时 |

### 预防方法

1. **不要 `wsl --unregister` docker-desktop** — 这是核武器。distro 坏了让它自己修复
2. **Docker Desktop 卡住时**：右键托盘图标 → Restart，不要 kill 进程
3. **WSL2 代理问题**：Docker Desktop Settings → Resources → Proxies → 设成 No Proxy
4. **终极方案**：不用 Docker Desktop，改用 WSL2 原生 Docker Engine（`service docker start`） — 它不需要 Docker Desktop 那套复杂的 backend/proxy 进程

---

## 二、AgentHub 用户场景分析

### AgentHub 的组件依赖

| 组件 | 用途 | 是否必须 Docker |
|------|------|:---:|
| PostgreSQL | 持久化数据 | 否（可 SQLite） |
| Redis | 缓存+L1记忆 | 否（可内存） |
| Backend (FastAPI) | API+WS+代理 | **否** |
| Frontend (React) | Web UI | **否** |
| claude CLI | AI 执行引擎 | **否** — 这是宿主机工具 |
| pi CLI | AI 执行引擎 | **否** — 这是宿主机工具 |

### 关键矛盾

把 `claude` 和 `pi` CLI 装在 Docker 里，然后通过 mount `D:\` 访问文件，这条路有根本缺陷：

1. mount 需要 Docker Desktop File Sharing 支持，且权限/性能都不如原生
2. CLI 需要联网调 API，Docker 里的网络又要过代理
3. 每次改 workspace 路径，Docker 里 mount 路径不同

**CLI Agent 天生属于宿主机，不应该放在 Docker 里。**

---

## 三、推荐架构（三选一）

### 方案 A：Docker 只跑服务，CLI 跑宿主机（推荐 MVP）

```
┌─ Docker ──────────────────────────┐
│  postgres:5432                     │
│  redis:6379                        │
│  backend:8000 (FastAPI)            │
└────────────────────────────────────┘
         ↑ API 调用
┌─ 宿主机 ───────────────────────────┐
│  frontend: npm run dev → :5173     │
│  claude CLI (cwd=D:\projects)      │
│  pi CLI (cwd=D:\projects)          │
└────────────────────────────────────┘
```

新用户部署步骤：
```bash
# 1. 启动服务（一次性）
docker compose up -d postgres redis backend

# 2. 启动前端
cd frontend && npm install && npm run dev

# 3. 安装 CLI（按需）
npm install -g @anthropic-ai/claude-code
npm install -g @earendil-works/pi-coding-agent
```

优点：
- Backend 调用 CLI 时直接 `create_subprocess_exec("claude", cwd=workspace)` — 原生文件访问
- Frontend 热更新开发
- Docker 只跑三个稳定服务，基本不会坏

缺点：
- 需要 Node.js 在宿主机
- 两个启动命令

### 方案 B：全 Docker（当前方案）

当前做法，已知问题：
- Docker Desktop 反复坏
- CLI 在容器里访问宿主机文件需要 mount
- 网络代理复杂

不推荐继续。

### 方案 C：全原生 + SQLite（零 Docker）

```
宿主机:
  SQLite (aiosqlite)
  Backend: python app/main.py
  Frontend: npm run dev
  claude / pi CLI
```

优点：
- 零 Docker 依赖，零部署问题
- 开发原型最快

缺点：
- 生产环境需要切回 PostgreSQL
- 并发性能受限

---

## 四、建议路线

| 阶段 | 做什么 |
|------|--------|
| **现在** | 方案 A：Docker 只跑 postgres+redis+backend，frontend 和 CLI 在宿主机 |
| **下个月** | Backend 加 `subprocess` 模块直接调宿主机 CLI（不再走容器内 claude） |
| **长期** | 如果做桌面版 → 方案 C + Electron/Tauri，一键安装 |

### 当前立即改动

最小改动实现方案 A：
1. `cli_runner/main.py` 已写（宿主机常驻进程）
2. Backend 保持 Docker
3. Frontend 用 `npm run dev` 在宿主机跑
4. 前端连 `localhost:8000`（Docker 端口映射）
5. CLI 宿主机直调，不需要 mount
