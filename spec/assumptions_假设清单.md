# AgentHub 显式假设列表

> 标记: ✅ 已确认 | 🔶 待确认 | ⚠️ 高风险

---

## 一、Agent 系统假设

| # | 假设 | 状态 |
|---|------|------|
| A1 | Claude Code CLI 可在无 GUI 环境运行，接受任意 provider 的 API 端点 | ⚠️ 需实测 |
| A2 | Codex CLI 可以通过环境变量切换 API base_url 指向非 OpenAI 端点 | ⚠️ 需实测 |
| A3 | TRAE 系统可通过 HTTP API 直接调用（非必须在 TRAE IDE 内） | ⚠️ 需实测 |
| A4 | 三个 Agent 系统的输出格式可统一为 SSE 流 + structured JSON | 🔶 |
| A5 | 用户持有至少一个 provider 的可用 API Key | 🔶 |

---

## 二、技术环境

| # | 假设 | 状态 |
|---|------|------|
| B1 | Docker 24+, Python 3.12+, Node.js 18+ 已安装 | 🔶 |
| B2 | 端口 8000/3000/5432/6379 未被占用 | 🔶 |
| B3 | pgvector/pgvector:pg16 可拉取 | 🔶 |
| B4 | PostgreSQL 单实例足够 MVP | ✅ |
| B5 | Redis 用作 Pub/Sub + 热上下文缓存足矣 | ✅ |

---

## 三、用户行为

| # | 假设 | 状态 |
|---|------|------|
| C1 | 用户熟悉飞书/微信式 IM | ✅ |
| C2 | 用户理解 @mention 概念 | ✅ |
| C3 | 用户在聊天窗口内完成审批操作 | ✅ |
| C4 | MVP 单用户本地运行（不需要多租户） | ✅ |

---

## 四、架构假设

| # | 假设 | 状态 |
|---|------|------|
| D1 | Coordinator Agent (LLM) 和 Harness (代码) 可干净分离 | ⚠️ |
| D2 | 5 层依赖倒置（L2 定义接口，L1 实现）可工程化执行 | 🔶 |
| D3 | Celery 足以支撑 MVP 任务队列 | ❌ REMOVED — v4 asyncio.gather 替代 |
| D4 | LLM 输出的 JSON Schema 总是可解析的 | ⚠️ |

---

## 五、数据

| # | 假设 | 状态 |
|---|------|------|
| E1 | 单会话消息 < 200 条 | ✅ |
| E2 | 20 条热上下文足够 | ✅ |
| E3 | AES-256-GCM 加密 API Key 安全可用 | ✅ |
| E4 | Agent name 全局唯一的约束可接受 | 🔶 |

---

## 六、外部依赖风险

| # | 风险 | 等级 |
|---|------|------|
| R1 | Agent 系统 CLI 行为与文档不一致 | ⚠️ 高 |
| R2 | LLM 输出不稳定导致 Harness 频繁拒绝 | ⚠️ 高 |
| R3 | 自定义 base_url 的 API 兼容性不足 | ⚠️ 高 |
