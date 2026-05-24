# 工作日志：前端 Agent 创建向导 + CLI 代理联调

- **谁**: 黎
- **日期**: 2026-05-24
- **分支**: `feature/domain2/frontend-agent-wizard`

## 目标

前端 Agent 创建流程优化 + CLI 代理模式端到端联调，确保用户通过 Web UI 创建 Agent 后可直接对话。

## 产出

- [x] **Agent 创建 3 步向导** — 选模板 → 配置(运行时/Provider/Model/BaseURL/Key) → 上线中(连通性测试+回滚)
- [x] **左侧面板优化** — 添加新建对话按钮，移除中间聊天区历史会话栏
- [x] **Mock 数据清理** — 移除 seed Agent（编辑/文案/研究员），仅从后端加载
- [x] **nginx 反向代理** — `/api` `/ws` `/proxy` 全部经 5173 端口，浏览器无需访问 8000
- [x] **前端相对 URL** — API/WS 请求走同源，不再硬编码 `localhost:8000`
- [x] **后端 bug 修复** — proxy URL 缺 `/proxy/` 前缀 / resume fallback 检测 DONE 事件 / HEAD 方法支持 / Provider 自由文本 / 迁移幂等 / 软删除名字可复用
- [x] **Docker 优化** — Dockerfile 加 Claude CLI + docker-compose 加 restart 策略
- [x] **Docker Desktop 部署验证** — 全链路通过（DeepSeek + MiniMax），MiMo 因 API 地址/鉴权待确认未通
- [x] **预提交 hook 修复** — 安装 pre-commit，解决 ruff RUF002/RUF003/B008 等 lint 问题

## 测试结果

| Provider | Agent | 状态 |
|----------|-------|------|
| DeepSeek | 技术负责人 | ✅ "Hi! How can I help you today?" |
| MiniMax | MM9097 | ✅ "Hey there, friend!" |
| MiniMax | 学妹 | ✅ 对话正常，system prompt 在 MiniMax 上可能不生效(模型内置 Claude 身份) |
| MiMo | 喵娘 | ❌ 400 Param Incorrect (API 地址或参数不对) |

## 关键决策

| 决策 | 原因 |
|------|------|
| 前端通过 nginx 反向代理而不是直连 8000 | Docker Desktop 端口转发在 WebSocket 下不稳定，单端口更可靠 |
| Provider 字段改为自由文本 | 代理只认 URL+Key，提供商标识不应受限 |
| 连通性测试失败回滚 Agent | 创建即删除，不给用户留脏数据 |
| 迁移 0002 幂等化 | `Base.metadata.create_all()` 从模型建表，后续 ADD COLUMN 会冲突 |

## 未完成 / 阻塞

- [ ] MiMo API 地址和鉴权方式待确认
- [ ] MiniMax system prompt 效果待验证（model 可能忽略自定义 persona）
- [ ] Docker Desktop 端口转发不稳定（nginx 反向代理绕过）

## 给下一位的交接

> 前端创建 Agent 流程已改为 3 步向导（`CreateAgentModal.tsx`），连通性测试在第 3 步。Agent 创建失败会回滚（后端删除 + 前端移除）。nginx 配置了 `/api` `/ws` `/proxy` 反向代理到 backend:8000，前端使用相对 URL（`.env` 中 `VITE_API_BASE_URL=` 和 `VITE_WS_BASE_URL=` 为空）。CLI 代理的 3 个 bug 已修复（proxy URL 前缀、resume fallback、HEAD 支持）。Provider 改为自由文本，新提供商只需填 URL+Key 即可接入。
