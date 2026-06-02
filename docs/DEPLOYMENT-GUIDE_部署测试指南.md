# AgentHub 部署与测试指南

> 版本：v2.0 | 日期：2026-05-30 | 支持两种部署模式

---

## 一、环境要求

| 组件 | 版本 | 验证命令 |
|------|------|---------|
| Python | 3.11+ | `python --version` |
| Node.js | 20+ | `node --version` |
| Docker | 24+ | `docker --version` |
| Claude Code CLI | 2.1+ | `claude --version` |

---

## 二、模式 A：纯 Docker（一键部署）

所有服务容器化，适合生产验证。

```bash
cd src/docker
docker compose up -d --build
```

| 服务 | 容器名 | 端口 |
|------|--------|------|
| PostgreSQL | agenthub-postgres-1 | 5432 |
| Redis | agenthub-redis-1 | 6379 |
| Backend | agenthub-backend-1 | 8000 |
| Celery | agenthub-celery_worker-1 | - |
| Frontend | agenthub-frontend-1 | 5174 |

**配置检查清单：**

- [ ] 根 `.env` 中 `SECRET_KEY` 与现有 Agent 加密密钥一致
- [ ] 根 `.env` 中 `PROXY_BASE_URL=http://localhost:8000`
- [ ] Agent 的 `base_url` 指向正确的 Provider 端点
- [ ] Agent 的 `api_key` 已配置

**重启：** `docker compose down && docker compose up -d --build`

---

## 三、模式 B：宿主机 + Docker 数据库（开发推荐）

PostgreSQL + Redis 在 Docker，Backend + Frontend 在宿主机。改代码无需 rebuild 镜像。

### 1. 启动数据库容器

```bash
cd src/docker
docker compose up -d postgres redis
```

### 2. 配置环境变量

编辑 `src/backend/.env`：

```env
DATABASE_URL=postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<与 Docker 部署保持一致>
PROXY_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

### 3. 启动后端

```bash
cd src/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 启动前端

```bash
cd src/frontend
npm install
npx vite --host 127.0.0.1
```

Vite 代理已配置 `/api` → `localhost:8000`，前端直接请求同源即可。

### 验证

```bash
curl http://localhost:8000/health       # → {"status":"ok"}
curl http://localhost:5173/api/agents   # → [] (via Vite proxy)
```

---

## 四、E2E 全链路验证

```bash
cd src/backend
python scripts/smoketest_e2e.py
```

验证步骤：Health → 创建 Agent → 创建 Session → WebSocket 发消息 → 收到 AI 回复 → 清理。

**预期：7/7 通过。**

也可手动验证：

```bash
# 1. 创建 Agent
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"name":"test","avatar":"T","role":"test","agent_system":"claude_code","provider":"deepseek","model":"deepseek-v4-pro","api_key":"sk-xxx","base_url":"https://api.deepseek.com/anthropic"}'

# 2. 创建 Session
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"type":"private","agent_id":"<agent_id>","title":"test"}'

# 3. WebSocket 连接测试（用 wscat 或前端 UI）
```

---

## 五、常见问题（v2.0 已知坑）

| # | 现象 | 根因 | 修复 |
|---|------|------|------|
| 1 | `InvalidTag` 解密失败 | SECRET_KEY 不匹配 | 确保根 .env 和 src/backend/.env 密钥一致，或重建 Agent |
| 2 | `bypassPermissions cannot be used with root` | Docker root 容器中 Claude CLI 限制 | 默认 permissionMode 已改为 acceptEdits |
| 3 | `ConnectionRefused` | proxy_base_url 指向错误端口 | PROXY_BASE_URL 设为 `http://localhost:8000` |
| 4 | `404 Not Found` 代理请求 | factory 重复拼接 /proxy/agents/{id} | 已修复，factory 只传 base url |
| 5 | `Content-Length` 不匹配 | 代理过滤 system 消息后未更新 header | 已修复，自动更新 content-length |
| 6 | 新建 Agent 不通 | Agent 缺少 api_key / base_url | 前端创建时填写完整 Provider 配置 |
| 7 | `model not found` | 模型名含 `[1m]` 后缀 | Agent model 字段用 `deepseek-v4-pro`（不带后缀） |

---

## 六、API 速查

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 列出 Agents / Providers
curl http://127.0.0.1:8000/api/agents
curl http://127.0.0.1:8000/api/providers

# 创建 Agent（完整配置）
curl -X POST http://127.0.0.1:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"name":"小助手","avatar":"🤖","role":"助手","agent_system":"claude_code","provider":"deepseek","model":"deepseek-v4-pro","api_key":"sk-xxx","base_url":"https://api.deepseek.com/anthropic"}'

# 创建 Session
curl -X POST http://127.0.0.1:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"type":"private","agent_id":"<id>","title":"chat"}'

# 单元测试
cd src/backend && python -m pytest tests/ -v

# Smoketest
cd src/backend && python scripts/smoketest_e2e.py
```

---

## 七、目录结构

```
AgentHub/
├── src/
│   ├── backend/        # FastAPI（5 层洋葱）
│   ├── frontend/       # React + TypeScript
│   └── docker/         # docker-compose + nginx
├── docs/               # 协作文档
├── skills/             # Claude Code Skills
├── scripts/            # 工具脚本
├── .env                # 根环境变量（Docker 读取）
└── worklogs/           # 工作日志
```
