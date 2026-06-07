# AgentHub 交付物索引（2026-06-07 凌晨冲刺收束）

> **plan_bcf9945c 5 task 全部 deliverable 落档 + verifier 复核 PASS**（详见 `worklogs/decisions/0011-plan-bcf9945c-complete.md`）

## 🎬 演示视频

- **最终视频**: AgentHub-Demo-Video.mp4 — 200s 1920x1080 h264+aac+mov_text 字幕 zho, 17.7 MB（文件暂缺）
- **视频脚本**: [`video/script.md`](./video/script.md) — 13KB 6 章节 demo 脚本
- **原始录屏**: [`video/raw-recording.mp4`](./video/raw-recording.mp4) — 200s 1920x1080, 14.5 MB
- **抽帧**: [`video/frame-{01,02,03}.png`](./video/) — 1-2 MB each
- **片头/片尾**: [`video/cover/cover-intro.png`](./video/cover/cover-intro.png) + [`cover-outro.png`](./video/cover/cover-outro.png) — AI 生成
- **TTS 配音**: [`video/voice/voice-001..007.wav`](./video/voice/) — matrix Chinese Male Announcer, 7 段
- **字幕**: [`video/subtitles.srt`](./video/subtitles.srt) — 27 entries

## 📊 集成报告

- **报告**: [`integration-verify-report.md`](./integration-verify-report.md) — 6 E2E 验证, 5/6 PASS at API+code
- **截图**:
  - [`screenshots/integration-01-s2-fullpage.png`](./screenshots/integration-01-s2-fullpage.png) — S2 群聊全页（真 backend 渲染）
  - [`screenshots/integration-02-s2-viewport.png`](./screenshots/integration-02-s2-viewport.png) — S2 群聊 viewport
  - [`screenshots/integration-03-agents-fullpage.png`](./screenshots/integration-03-agents-fullpage.png) — AI 列表全页（11 agents）
  - [`screenshots/integration-04-agents-viewport.png`](./screenshots/integration-04-agents-viewport.png) — AI 列表 viewport

## 📚 飞书文档

- **AI 协作开发记录**: [`AI协作开发记录.md`](./AI协作开发记录.md) — 12.1KB CJK 3214, 6 段 a-f（团队介绍/工作流/ADR 索引/worklogs 模板/收束 4 阶段/截图引用）
- **PRD 增量**: `../plan/PRD_AgentHub_统一方案.md` — 顶部「实施进度速览」+ 末尾「AI 协作沉淀」（commit `602026f` + `82b265a`）

## 💻 代码（git commits on `feature/frontend/pin-ui`）

| Commit | Task | 变更 |
|--------|------|------|
| `e49df82` | P0-1 | WebPreviewCard iframe sandbox |
| `13fbfeb` | P0-2 | DiffView 彩色 diff |
| `2f8d9fc` | P0-3 | 新聊天 1v1 流式 |
| `3d60216` + `227055a` | P0-6 | 附件上传 multipart |
| `e667579` + `57e4859` | P0-4 | Pin UI 初版 |
| `32485a1` | P0-5 + P0-4 schema-钉死 | 复制代码/重新生成 + test |
| `602026f` | docs-feishu v1 | PRD rename + 增量 |
| `82b265a` | docs-feishu v2 | CJK 1868→3214 + 12 链接修复 |

## ⚠️ 已知 gap（明早向用户披露）

1. E 视觉 S5 inbox 3 重 gap（backend TODO / frontend mock / UI 无 nav）— M4 TODO
2. S3 私聊 UI 不可达（ChatView mock-driven）— S2 group 真 backend 渲染 OK
3. Pin API 无 session 所有权校验 — 需 backend 修复
4. Docker backend image 6h old 缺 `/api/attachments/*` — F 测试用 local uvicorn :8766
5. 视频 v4 录屏 DISPLAY1 wallpaper 残留（v5 Win32 SetWindowPos + ffmpeg crash 失败）— 已透明声明

## 📐 ADR & Decisions

- `worklogs/decisions/0001-cli-first-pivot.md` — CLI 优先
- `worklogs/decisions/0002-长驻 CLI.md` — 长驻 CLI
- `worklogs/decisions/0003-MCP URL+AP-05 暂缓.md` — MCP URL
- `worklogs/decisions/0004-MCP F1 落地口径+安装探针.md`
- `worklogs/decisions/0005-attach.md` — F2 attach
- `worklogs/decisions/0006-MCP 注入.md`
- `worklogs/decisions/0007-Tauri 桌面.md`
- `worklogs/decisions/0008-self-governance-authorization.md` — 用户授权 owner 自主决策
- `worklogs/decisions/0009-p2-handoff-cron.md` — P2 兜底 cron 计划（已删）
- `worklogs/decisions/0010-integration-verify-downscope-e.md` — E 视觉 downscope
- `worklogs/decisions/0011-plan-bcf9945c-complete.md` — plan 收束（本文件主决策）
