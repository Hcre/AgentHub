# AgentHub 部署与测试指南

> 版本：v1.1 | 日期：2026-05-24 | 更新：前端启动方式 + Docker 部署 + 缓存问题

---

## 一、环境要求

| 组件 | 版本/说明 | 验证命令 |
|------|----------|---------|
| Python | 3.12+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| PostgreSQL | 16+ | `pg_isready` |
| Redis | 7+ | `redis-cli ping` |
| Claude Code CLI | 2.1+ | `which claude && claude --version` |
| npm | 10+ | `npm --version` |

### Claude Code CLI 认证

```bash
# 验证 CLI 可用（能正常响应即表示已认证）
claude --print "hi" --max-turns 1
```

如果未安装：
```bash
npm install -g @anthropic-ai/claude-code
```

---

## 二、首次部署

### 1. 克隆 + 安装依赖

```bash
git clone https://github.com/Hcre/AgentHub.git
cd AgentHub

# 后端
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# 前端
cd frontend
npm install
cd ..
```

### 2. 环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，确认：
#   DATABASE_URL=postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub
#   REDIS_URL=redis://localhost:6379/0
#   SECRET_KEY=<有效的 base64 32 字节密钥>
#   PROXY_BASE_URL=http://127.0.0.1:8000/proxy  ← CLI 代理模式必填
```

### 3. 创建数据库

```bash
sudo -u postgres psql -c "CREATE USER agenthub WITH PASSWORD 'agenthub_dev_pwd';" || true
sudo -u postgres psql -c "CREATE DATABASE agenthub OWNER agenthub;" || true
```

### 4. 初始化表结构

```bash
cd backend
source .venv/bin/activate
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.infrastructure.db.base import Base
import app.infrastructure.db.models  # noqa: F401

async def main():
    e = create_async_engine('postgresql+asyncpg://agenthub:agenthub_dev_pwd@localhost:5432/agenthub')
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('OK')
    await e.dispose()
asyncio.run(main())
"
```

**⚠️ 踩坑 1：表创建后如果有新增字段，需手动执行 migration。**

当前需要补的列（如果表已存在）：
```sql
ALTER TABLE agents ADD COLUMN IF NOT EXISTS agent_system VARCHAR(32) DEFAULT 'mock' NOT NULL;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS base_url VARCHAR(512);
```

---

## 三、启动服务

### 本地开发启动

#### Terminal 1 — 后端

```bash
cd backend
source .venv/bin/activate
alembic stamp head                          # 对齐 migration 版本
uvicorn app.main:app --reload --port 8000
```

#### Terminal 2 — 前端

```bash
cd frontend
npm run build && npm run preview -- --port 4173
```

⚠️ **不要用 `npm run dev`**：Vite 开发服务器有预构建缓存问题，切换分支/重装依赖后 CSS 可能缺失（表现为弹窗不居中、组件错位）。详情见 §七 Q8。

#### 验证启动

```bash
# 后端
curl http://127.0.0.1:8000/api/agents

# 前端（预览地址为 4173）
curl http://127.0.0.1:4173
```

### Docker 部署

```bash
cd docker
docker compose up -d --build
```

服务端口：

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8000 | FastAPI + Uvicorn |
| 前端 | 5173（映射到容器 80） | Nginx 托管生产构建 |
| PostgreSQL | 5432 | pgvector/pg16 |
| Redis | 6379 | Redis 7 |

⚠️ **Docker 不支持 claude_code 运行时**：容器内无 Node.js + Claude CLI，只能用 `anthropic_api`（直连）或 `mock`（演示）。

Docker 环境变量在项目根目录 `.env` 中（`docker-compose.yml` 引用 `../.env`），需确认以下字段：

```bash
# 根 .env 额外需要（Docker 用）：
PROXY_BASE_URL=http://backend:8000/proxy   # 容器内用 service name
```

---

## 四、测试 Claude Code 适配器

### 4.1 单元测试

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v --no-cov
```

预期：38 passed

### 4.2 E2E 多轮对话测试

确保后端已启动（Terminal 1），然后：

```bash
cd backend
source .venv/bin/activate
python scripts/manual_test_claude.py
```

测试脚本自动完成：创建 agent → 创建 session → 3 轮 WS 对话。

验证点：

| # | 预期 |
|---|------|
| 1 | Agent 创建返回 201，`agent_system: "claude_code"` |
| 2 | 首轮对话正常响应 |
| 3 | 第二轮 `--resume` 恢复上下文，Agent 记住第一轮内容 |
| 4 | 第三轮正常结束 |
| 5 | 每轮输出 `[DONE] cost=$x.xxxx time=xxxxms` |

### 4.3 前端 UI 测试

1. 浏览器打开 `http://localhost:5173`
2. 通过 API 创建 Agent 和 Session（见 4.2 的脚本或手动 curl）
3. 进入对应 Session 发送消息
4. 观察流式输出 + 工具调用 + 多轮记忆

---

## 五、常见问题

### Q1: `ModuleNotFoundError: No module named 'app'`

**原因：** 不在 backend 目录下运行 uvicorn。

**解决：** `cd backend` 后再启动。

### Q2: `[Errno 98] address already in use`

**原因：** 8000 端口被上次未关闭的进程占用。

**解决：**
```bash
kill $(lsof -t -i:8000)
```

### Q3: `Internal Server Error` on create agent

**原因：** agents 表缺少 `agent_system` / `base_url` 列。

**解决：** 执行 §二.4 的 ALTER TABLE 语句。

### Q4: `Nonce must be between 8 and 128 bytes`

**原因：** 创建 agent 时未传 `api_key`，工厂对空字符串调了解密函数。

**状态：** 已在 factory.py 修复（空值时跳过解密）。如果仍遇到，确认代码是最新版本。

### Q5: `No conversation found with session ID: xxx`

CLI session 被手动删除或过期。系统会自动 fallback 新建，不影响功能。

### Q6: Claude Code CLI 响应超时

默认超时 300s。检查：
- CLI 是否已认证：`claude --print "hi" --max-turns 1`
- 网络是否可达 Anthropic API
- 超时可在 Agent settings JSON 中调整 `"cli_timeout": 600`

### Q7: 前端 502 Bad Gateway

后端未启动或端口不是 8000。前端 `.env` 的 `VITE_API_BASE_URL` 必须匹配后端端口。

### Q8: 前端样式错乱（弹窗不居中、组件缺位）

**原因：** Vite 开发服务器（`npm run dev`）使用 `node_modules/.vite` 预构建缓存。切换分支/重装依赖后，缓存中的 CSS 可能不包含新组件的 Tailwind 类名（如 `fixed`、`inset-0`）。

**解决方案：**

方案 A（推荐）—— 使用生产预览替代开发服务器：
```bash
npm run build && npm run preview -- --port 4173
```

方案 B —— 清除缓存后重启 dev：
```bash
rm -rf node_modules/.vite node_modules dist
npm install
npm run dev
```

**原理：** `npm run build` 全量扫描源码生成完整 CSS，无缓存。`npm run dev` 按需增量生成 + 缓存复用，缓存过期会导致新类名缺失。

### Q9: Docker 和本地的前端显示不同

Docker 走 `npm run build` 生产构建，本地 `npm run dev` 可能缓存过期。统一用 §三 的 `npm run build && npm run preview` 即可一致。

---

## 六、API 速查

```bash
# 创建 claude_code Agent
curl -X POST http://127.0.0.1:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"name":"测试Agent","avatar":"🤖","role":"开发","agent_system":"claude_code","provider":"anthropic"}'

# 列出所有 Agent
curl http://127.0.0.1:8000/api/agents

# 创建私聊 Session
curl -X POST http://127.0.0.1:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"type":"private","agent_id":"<agent_id>","title":"test"}'

# 列出 Session
curl http://127.0.0.1:8000/api/sessions

# 获取 Session 历史消息
curl http://127.0.0.1:8000/api/sessions/<session_id>/messages

# WebSocket 连接
wscat -c ws://127.0.0.1:8000/ws/sessions/<session_id>
# 发送: {"type": "message", "content": "你好"}
```

---

## 七、相关文档

| 文档 | 内容 |
|------|------|
| `docs/adapter-cli-flow-analysis.md` | 7 个场景的 CLI 调用流程 |
| `docs/DOC-15-claude-adapter-design.md` | 双轨架构设计 |
| `决策/dong/踩坑记录-ClaudeCode适配器联调.md` | 联调踩坑详细记录 |
| `skills/test-claude-adapter.md` | 测试 Skill |
