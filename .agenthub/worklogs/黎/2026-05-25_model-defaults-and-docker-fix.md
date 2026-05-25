# 工作日志：模型默认值更新 + Docker Desktop 集成 + 弹窗修复

- **谁**: 黎
- **日期**: 2026-05-25
- **分支**: `feature/domain2/frontend-agent-wizard`

## 目标

修复前端体验问题 + Docker Desktop 网络配置 + 三模型端到端验证。

## 产出

- [x] **模型默认值更新** — DeepSeek→deepseek-v4-pro[1m]，MiniMax→MiniMax-M2.7，MiMo→mimo-v2.5-pro
- [x] **MiMo API Key 更新** — 获取有效 MiMo Key（sk-clm...），三模型 API 全通
- [x] **弹窗关闭修复** — status 初始值 'creating' 改为 'idle'，避免关闭被拦截
- [x] **Model 输入框优化** — 选 Provider 自动填入默认 Model + placeholder 提示
- [x] **Docker Desktop 集成** — 停用 WSL 内 Docker Engine，启用 Desktop WSL 集成，WebSocket 正常
- [x] **系统提示词验证** — 三模型均能跟随 system prompt（需强硬措辞覆盖内置身份）

## 测试结果

| Provider | Model | API | System Prompt |
|----------|-------|-----|---------------|
| DeepSeek | `deepseek-v4-pro[1m]` | ✅ | ✅ 完全跟随 |
| MiniMax | `MiniMax-M2.7` | ✅ | ✅ 完全跟随 |
| MiMo | `mimo-v2.5-pro` | ✅ | ✅ 完全跟随(需正确Key) |

> MiniMax/MiMo 模型内置 Claude 自我认知，需要强硬的 system prompt 才能覆盖（如 "你必须扮演xxx，绝对不能说自己是Claude"）。

## 关键决策

| 决策 | 原因 |
|------|------|
| Docker Desktop WSL 集成替代独立 Engine | 统一守护进程，避免端口转发双打 |
| Model 保留自由输入 + 自动填入 | Provider 切换时 model 不匹配，placeholder 提示默认值 |
| 工作日志按日期拆分新文件 | 按 skill 规范，每天独立日志 |

## 给下一位的交接

> Docker Desktop 需在 Settings → Resources → WSL Integration 勾选 Ubuntu。前端 Agent 创建弹窗已稳定，Model 输入框在切换 Provider 时自动填入默认值。三模型 API 和 system prompt 路径已打通。
