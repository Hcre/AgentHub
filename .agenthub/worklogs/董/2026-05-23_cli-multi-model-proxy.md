# 工作日志：CLI 多模型代理实现

- **谁**: 董
- **日期**: 2026-05-23
- **分支**: feature/domain2/cli-custom-model
- **关联 Spec**: `docs/PRD_AgentHub_v4_统一方案.md`, `.agenthub/worklogs/董/解决cli只能接入官方api问题/cc-haha-multi-model-analysis.md`

## 目标

解决 Claude Code CLI 只能调用 Anthropic 官方 API 的限制，使其支持 DeepSeek、Kimi、GLM 等第三方模型。

## 产出

- [x] **cc-haha 机制分析** — 深入分析 cc-haha 的多模型支持机制：环境变量注入 + 协议转换代理 + Provider 预设 + 会话级隔离
- [x] **CLI 多模型代理方案** — 设计文档：`解决cli只能接入官方api问题/CLI多模型代理方案.md`
- [x] **代理模块实现**:
  - `backend/app/infrastructure/llm/proxy/__init__.py` — 模块导出
  - `backend/app/infrastructure/llm/proxy/handler.py` — ProxyHandler（鉴权适配 + URL 路由 + 流式透明转发）
  - `backend/app/api/routers/proxy.py` — 代理路由（`/proxy/agents/{agent_id}/{path:path}`）
- [x] **Runtime 适配**:
  - `claude_code_runtime.py` — `_build_env()` `ANTHROPIC_BASE_URL` 改为指向本地代理，支持代理/全局双模式
  - `factory.py` — CLAUDE_CODE 分支传入 `agent_id` + `proxy_base`
- [x] **应用装配**:
  - `config.py` — 新增 `proxy_base_url`
  - `main.py` — 注册 proxy router + httpx 共享客户端生命周期管理
- [x] **导入验证通过** — proxy router、ProxyHandler、_build_env、factory 全部正常加载

## 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 所有 CLI 流量统一过代理，不直连 | 第三方鉴权机制不兼容（x-api-key vs Bearer Token），直连前提不可靠 | 统一代码路径，鉴权适配集中在代理层 |
| `ANTHROPIC_BASE_URL` 改为 `{proxy_base}/agents/{agent_id}` | URL 路径编码 agent 身份，无需自定义 header | 每次请求代理自动定位到正确 Agent 配置 |
| pass-through 优先，协议转换后置 | DeepSeek/Kimi/GLM 已原生支持 Anthropic 协议，GPT/Qwen 只是少数 | 覆盖 80% 场景，初始改动量 <200 行 |
| 支持代理/全局双模式 | `proxy_url` 为空时继承当前 shell 环境，兼容全局 Claude Code 配置 | 不影响现有用户自己的 CLI 使用 |

## 架构变更

```
修改前（直连）:
CLI → ANTHROPIC_BASE_URL=agent.base_url → 直接调第三方 API
                                           ↑ 鉴权不兼容风险

修改后（代理）:
CLI → ANTHROPIC_BASE_URL={proxy}/agents/{id} → ProxyHandler
    → 鉴权适配 → 转发 agent.base_url → 第三方 API
```

## 文件清单

```
新增 (3):
  backend/app/infrastructure/llm/proxy/__init__.py
  backend/app/infrastructure/llm/proxy/handler.py
  backend/app/api/routers/proxy.py

修改 (6):
  backend/app/core/config.py                             (+proxy_base_url)
  backend/app/infrastructure/llm/claude_code_runtime.py  (__init__ + _build_env)
  backend/app/infrastructure/llm/factory.py              (传入 agent_id/proxy_base)
  backend/app/api/routers/__init__.py                    (+proxy export)
  backend/app/main.py                                    (+proxy router + httpx 生命周期)
  backend/tests/test_claude_code_runtime.py              (适配新签名)
```

## 未完成 / 阻塞

- [ ] **端到端验证** — 需要一个真实的 DeepSeek API Key 创建 Agent → 发送消息 → 验证代理转发链路和流式响应完整性
- [ ] **测试更新** — `test_claude_code_runtime.py` 需按 `_build_env` 新逻辑更新断言
- [ ] **协议转换模块** — GPT/Qwen 接入（后续需求）

## 给下一位的交接

> **代理工作原理**：用户创建 Agent 时配置 `base_url` 和 `api_key`，Chat 调用时 CLI 子进程自动设置 `ANTHROPIC_BASE_URL` 指向 `http://127.0.0.1:8000/proxy/agents/{id}`。CLI 的所有 API 请求经过 ProxyHandler → 解密 agent 的 api_key → 注入 `x-api-key` → 流式转发到 `{agent.base_url}/{path}`。CLI 完全无感知。
>
> **验证方法**：
> 1. 创建 Agent：`curl -X POST http://127.0.0.1:8000/api/agents -H "Content-Type: application/json" -d '{"name":"test","avatar":"x","role":"x","agent_system":"claude_code","model":"deepseek-v4-pro","base_url":"https://api.deepseek.com/anthropic","api_key":"sk-xxx"}'`
> 2. 创建 Session → 发送消息 → 观察 backend 日志中的 `proxy <agent_id> → https://api.deepseek.com/anthropic/v1/messages` 日志行
> 3. 确认流式响应正常
>
> **设计文档**: `.agenthub/worklogs/董/解决cli只能接入官方api问题/CLI多模型代理方案.md`
> **参考分析**: `.agenthub/worklogs/董/解决cli只能接入官方api问题/cc-haha-multi-model-analysis.md`
