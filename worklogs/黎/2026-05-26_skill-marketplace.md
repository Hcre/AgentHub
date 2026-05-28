# 2026-05-26 — 技能市场 + 聊天持久化 + 目录分离

## 做了什么
- 后端 `POST /api/skills/marketplace/search` 代理 skillsmp.com，按 star 排序
- 后端 `POST /api/skills/marketplace/install` 通过 GitHub Contents API 递归拉取 skill 目录（含 scripts 等）
- 前端 `SkillMarketplacePage`：搜索卡片网格 + 一键安装
- `.agenthub/skills/` 放运行时 skill（应用 Agent 用），`skills/` 放开发 process skill
- `chatStore` 加 Zustand persist 中间件，localStorage 持久化，刷新不丢聊天记录
- 创建 Agent 弹窗跳转市场时保存草稿，返回后恢复
- 前端 nginx 去 default.conf 冲突 + 启动顺序 depends_on

## 给下一位的交接
- 市场数据源 skillsmp.com，搜索用 `sortBy=stars`
- GitHub API 限流 60次/h，大量安装需要加 token
- Docker Desktop 5173 端口被 WSL relay 占用，前端改用 5174
