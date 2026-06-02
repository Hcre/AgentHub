# 工作日志：Agent Workspace 合并 main + 部署修复

- **谁**: 黎
- **日期**: 2026-05-30
- **分支**: feature/domain2/agent-workspace
- **关联 Spec**: 无

## 目标
合并 main 分支 39 个 commit（目录重构），修复部署问题，两种模式验证通过。

## 产出
- [x] 671d839 — fix: 修复 Docker 部署 4 个 bug
- [x] c604eea — docs: 文档统一清理
- [x] 合并 main 39 commits（`f03802f`）
- [x] 宿主机 + Docker 混合部署验证通过
- [x] 纯 Docker 部署验证通过
- [x] E2E 链路：前端 → WS → 后端 → CLI → 代理 → DeepSeek 全通

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| `bypassPermissions` → `acceptEdits` | Docker root 容器中 Claude CLI 拒绝 bypassPermissions | 容器部署默认权限 |
| factory.py 去重 proxy_url 拼接 | 代理路径重复拼接导致 404 | 只传 `proxy_base_url`，runtime 自己拼 |
| proxy handler 修 Content-Length | DeepSeek 过滤 system 消息后 body 变化但 header 未更新 | HTTP 协议合规 |
| SECRET_KEY 同步到根 .env | 目录重构后根 .env 密钥与旧数据不匹配 | 现有 Agent 可解密 |

## 给下一位的交接
> 两种部署方式都可用：
> 1. 纯 Docker：`cd src/docker && docker compose up -d`
> 2. 宿主机：Docker 跑 PG+Redis，本地 `uvicorn` + `npx vite`
> 每次部署后 API Key 加密依赖 SECRET_KEY，换密钥需重建 Agent。
