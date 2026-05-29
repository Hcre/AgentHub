# 域3：工具链与产物 — 任务清单

> 职责：Diff 预览、网页预览、部署、Git 管理、上下文持久化、CLI、PWA
> 技术栈：Monaco + diff2html (Diff) + Docker (部署) + Workbox (PWA) + Click (CLI)

---

## 一、域3 系统范围

```
┌─ 前端 ──────────────────────────────┐
│ DiffCard: Monaco + diff2html         │
│ PreviewCard: iframe Sandbox          │
│ DeployCard: 部署状态卡片              │
│ CLI: Click + Rich + prompt_toolkit  │
│ PWA: Workbox + Manifest + IndexedDB │
└────────────┬────────────────────────┘
             │ REST + WS
┌────────────┴────────────────────────┐
│ L3/L2                                │
│ Diff 生成 (unified diff)             │
│ Vite Dev Server 管理 (预览)           │
│ Docker + GitHub Actions (部署)        │
│ GitPython (版本管理)                  │
│ 三层上下文 (热/长期/历史)              │
└────────────┬────────────────────────┘
             │
┌────────────┴────────────────────────┐
│ L1                                   │
│ FileSystem (Sandbox + Virtual)       │
│ GitPython / Docker SDK              │
│ docs/.agenthub/ 文件系统                  │
│ IndexedDB (PWA 离线)                 │
└─────────────────────────────────────┘
```

---

## 二、全部任务

### M1（5/20-22）：基础

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 3.1 | Docker Compose (PG+Redis+FastAPI) | 4h | 一键启动全部服务 |
| 3.2 | .env.example + Makefile | 2h | install/dev/test/build 命令 |

### M2（5/23-27）：代码渲染 + 上下文

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 3.3 | 代码块语法高亮 (Monaco Editor 基础) | 4h | 代码可读 |
| 3.4 | 热上下文 (Redis 20条滑动窗口) | 4h | Agent 引用前几条消息 |
| 3.5 | 长对话压缩 (LLM 摘要) | 4h | >20条自动压缩 |

### M3（5/28-6/1）：Git + 上下文

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 3.6 | GitPython 封装：auto commit + 冲突检测 | 6h | Agent 修改后自动 commit |
| 3.7 | Agent 文件读写安全 (路径校验/黑名单) | 4h | ../ 和 .env 拒绝 |
| 3.8 | AgentFileSystem (Virtual FS + 权限检查) | 4h | 读/写/审批分流 |

### M4（6/2-5）：预览 + 部署 + 持久化

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 3.9 | Diff 预览全栈：unified diff → diff2html 卡片 | 8h | 绿/红标注，每文件 Tab |
| 3.10 | 网页预览：Vite Dev Server + iframe Sandbox | 6h | 点击预览→iframe 渲染 |
| 3.11 | 一键部署：Docker build → push → deploy | 8h | 状态卡片(building→deploying→deployed) |
| 3.12 | Pin 消息 + 长期上下文 (PostgreSQL) | 4h | Pin 后跨会话可见 |
| 3.13 | 历史预览 (本地 docs/.agenthub/ 归档) | 2h | "查看完整对话"展开 |

### M5（6/6-9）：多端 + 测试

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| 3.14 | CLI 工具 (agenthub chat/send/agent) | 8h | 终端完整聊天 |
| 3.15 | PWA: Workbox + Manifest + IndexedDB | 6h | 手机安装+离线查看 |
| 3.16 | E2E 测试 (Playwright 覆盖 5 Story) | 8h | 全绿 |
| 3.17 | 压力测试 (10 并发) | 4h | 无延迟 |

---

## 三、工时汇总

| M | 工时 |
|----|------|
| M1 | 6h |
| M2 | 12h |
| M3 | 14h |
| M4 | 28h |
| M5 | 26h |
| **合计** | **86h** |

---

## 四、关键文件

```
src/backend/app/
├── tools/
│   ├── diff_preview.py        # unified diff 生成
│   ├── web_preview.py         # Vite Dev Server 管理
│   ├── deploy.py              # Docker + GH Actions
│   └── git_manager.py         # GitPython 封装
├── infrastructure/
│   ├── file_system.py         # AgentFileSystem (权限+锁)
│   └── sandbox.py             # 路径安全校验

src/frontend/src/
├── components/cards/
│   ├── DiffCard.tsx           # diff2html Monaco
│   ├── PreviewCard.tsx        # iframe sandbox
│   └── DeployCard.tsx         # 部署状态
└── services/
    └── deploy.ts              # 部署状态轮询

cli/                           # Phase M5
ide-plugin/                    # Phase M5
src/frontend/public/sw.js          # PWA Service Worker
```
