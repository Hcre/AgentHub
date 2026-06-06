# AgentHub AI 协作开发记录

> 项目：AgentHub — IM 聊天式多 Agent 协作平台 · 周期：2026-05-20 → 2026-06-07（M1→M5 收尾冲刺）
> 仓库：GitHub `oldmanpushbike/agenthub`（feature 分支并入 main）
> 本文档定位：交付物 3「AI 协作开发记录」——飞书文档同步介绍协作流程与产物

---

## a. 团队介绍

AgentHub 由 **3 位人类开发者 + 1 位 Claude Agent** 共同完成，遵循「Opus 开发 + DeepSeek 审查 + 人决策」的角色分工（[`01-角色分工与文件体系.md`](conventions/ai-workflow_AI协作开发流程/01-角色分工与文件体系.md)）：

- **董**（git: yii.d）——协调者 + 域 2 DRI。任务编排、记忆系统（B 方向）、CLI 多模型代理、群聊编排、`MCP save_memory` 端到端打通。
- **黎**（git: oldmanpushbike）——全栈 + 域 3 DRI。39 commits 合并、ProviderKeyResolver、OpenCode 集成、桌面 App 选型（Tauri 2 + 瘦客户端，ADR-07）。
- **袁**（git: xiangbianpangde）——规范架构 + MCP DRI。模板重构、全栈目录整合、MCP 计划/PRD/收束报告 F1+F2、集成验证。
- **Claude Agent**（Opus）——架构师 + 开发者。架构设计、计划审查、TDD 自检、写代码、修 bug、生成文档（git identity 自动归「袁」目录）。

**协作心法**：Claude 不自审自己的代码——TDD 是自检（保证「按预期运行」），DeepSeek 是独立审查关卡（发现「视角盲区」）。人只在审查者标记的差异点和高风险项上做决策。

---

## b. 工作流：CLAUDE.md → conventions → specs → worklogs → STATUS → dashboard

协作流程是一条**自上而下、可追溯、可视化**的链路：

1. **CLAUDE.md** 冷启动契约：每个新会话从 `git config user.name` 自动判断「你是谁」，加载对应 worklog 目录、当前进度、阻塞项。无须人类口头交代上下文。
2. **docs/conventions/**（01-10）是 AI 红线速查表：`AR-01 5 层洋葱 / CR-12 禁同步阻塞 / PR-02 feature 分支命名 / AP-02 错误信封 / T-01 独立测试 / D-05 文档命名`。
3. **docs/specs/**（00-05 + domains/）是 BDD 验收契约：每个功能点对应 API 冻结、数据模型、5 条 Core User Stories，代码必须能让 BDD 跑通。
4. **worklogs/{人名}/YYYY-MM-DD_*.md** 是「给下一位的交接」：每份末尾固定 `## 给下一位的交接` 段，让接手的人 2 小时内能继续。
5. **STATUS.md** 是进度数据源（自己的行 + 交接段 + 技术债）。
6. **dashboard.html** 是物理可观测层：`scripts/check_worklog.py` 校验 STATUS 与 git log 一致；dashboard 暖色 Claude 风（焦糖色 + Songti SC 衬线）渲染进度图，demoscene 可读。

---

## c. ADR 索引（10 份架构决策记录）

`worklogs/decisions/` 是 AgentHub 的「决策记忆」——记录**为什么选 A 不选 B**、当时选项、权衡依据、未来影响。仅在收束节点提升。

**核心 10 份**：

1. **0001 CLI 优先**：API 95h+ 自建 Harness 不可行 → CLI 模式（Claude Code 自带 tool/state/Permission）<300 行 + SessionStore（Redis 7d TTL）。
2. **0002 Phase 1 长驻 CLI**：spawn+EOF 短驻 → stdin 持久监听 + stream-json 长驻；灰度开关 `CLAUDE_CODE_LONG_RUNNING=1`。
3. **0003 MCP URL = `/api/mcp`**：对齐现状（全库无 `/v1/`），AP-05 暂缓进 NB-02 backlog；记忆 MCP 协议端 mount 移到 `/api/mcp-memory`。
4. **0004 MCP F1 二次对账**：计划写「FK→workspaces」实无该表 → 裸 UUID stand-in；安装=结构校验探针（422 拦截非法配置）而非拉起进程。
5. **0005 attach = 请求携带**：`AgentRequest.mcp_servers` 逐调用带 config（非运行时有状态，避免池化跨 agent 串号）。
6. **0006 MCP 注入逐调用隔离通道**：claude_code `--mcp-config <tmp>` / opencode `OPENCODE_CONFIG=<tmp>`（逐进程 env）；pi_agent 本机无可验证保留 deferred。
7. **0007 Tauri 2 桌面 App 转向**：5 路径对比 → **Tauri 2 + 瘦客户端（M2）+ GitHub Releases**；3-5MB vs Electron 100MB+。
8. **0008 owner 自决授权**：用户明早未到岗期间 owner 自主判断（verifier FAIL retry / steer / 改 prompt），**不可删用户文件 / 不可 force push main**。
9. **0009 P2 兜底 cron**：2026-06-07 10:00 用户未报备 → cron 自动启动 P2 接力（MCP P3 F3 创建 / P4 F5 展示）。
10. **0010 集成验证 E downscope**：Inbox 视觉 M4 TODO（不在 P0 范围）→ 5/6 PASS override_accept；视频脚本用 S2 群聊真 backend 渲染。

**方法论固化**（ADR-04/06 沉淀）：凡「N 个组件都能做 X」必须逐个打开验证 X 在每个组件里可行——避免 R11「opencode 也能注入 MCP」未经实测断言。ADR-06 据此实测发现 opencode 的 `OPENCODE_CONFIG` env 才是逐调用隔离通道（不是写全局），R11 的「写全局会串号」根因不成立 → opencode 拉回本期。

---

## d. worklogs 目录结构 + 模板

**目录布局**（`worklogs/{Git 用户名 → 中文名}/`）：

```
worklogs/
├── template.md                              # 通用模板（交接段是核心）
├── decisions/                                # ADR 仓库（0001-0010）
├── 董/   黎/   袁/                          # 三人 worklog 目录
```

**命名规范**（D-05 文档规范）：`YYYY-MM-DD_<一句话简短描述>.md`；禁止 v1/v2 序号、重复描述、空标题。

**Git ↔ 人名映射**（`STATUS.md` + `scripts/check_worklog.py` 自动校验）：`oldmanpushbike` → 黎、`yii.d` → 董、`xiangbianpangde` → 袁。

**worklog 模板核心段**（`worklogs/template.md`）：固定 6 段——`## 目标`（一句话） / `## 产出`（commit hash + 文件 + 验证） / `## 关键决策`（表格：决策/原因/影响 → 收束节点评审是否提升 ADR） / `## 未完成 / 阻塞` / `## 给下一位的交接`（接手的人 2 小时内能继续）。

**`scripts/check_worklog.py` 自动化检查**（pre-commit hook 触发）：push 时校验「我今天 commit 了 → 我今天的 worklog 必须存在」——避免「代码上线了日志没写」丢历史。

---

## e. 收束报告 4 阶段方法论（整理 / 测试 / 审计 / 验证）

**强制流程**——跳过 = 后续功能点不通过。AI 不自动启动收束，但 AI **会拦住**越过闸门的开发（[`06-第三步_收束节点.md`](conventions/ai-workflow_AI协作开发流程/06-第三步_收束节点.md)）。

```
收束节点 = 质量闸门（每 3 个功能点或版本变更触发）
阶段1 整理 ──→ 阶段2 测试 ──→ 阶段3 审计 ──→ 阶段4 验证
 代码/文件    全量+集成+回归   AI+人双线    BDD+用户故事
```

**阶段 1 整理**：消除本批次熵增。ruff 清未用 import / 删注释代码 / `worklogs/` 齐全 / 过时文档归档 `archive/` / **回顾 worklog 关键决策 → 提升 ADR** / FILE_GRAPH 同步。

**阶段 2 测试**：CI 增量不做的全量。全量单测 + 集成 + 跨模块回归 + 手工探索 3-5 条核心用户流程 + 性能基准对比（vs 上收束节点，>20% 退化即标记）。

**阶段 3 审计**（AI + 人双线，互不替代）：
- **AI 线**：架构 AR-01/02/06 + 代码 CR-01-12 + Git PR-01-09 + API AP-01-07 + 测试 T-01-06 + 图谱缺陷 = 全量模式扫描。**AI 不判断对错，只标记疑点**。
- **人线**：AI 标记项复核 + 业务逻辑合理性 + 设计意图偏离 + PR/CR 抽查 + 主观质量。
- **双线合入**：🔴 红线必修 / 🟡 中风险接受须 ADR。

**阶段 4 验证**：「做完了 ≠ 做对了」。BDD 场景逐条回演 + 可视化产出重新生成（Playwright 截图对比）+ 回到 `docs/plan/背景.md` 验证方向未偏 + 技术债盘点。

**核心原则 4 条**（项目红线）：

1. **先收束再前进**——收束是「不做完不能走」，不是「建议做完」
2. **AI + 人双线**——AI 模式匹配 / 人理解上下文，互补不替代
3. **效果验证 ≠ 功能测试**——BDD 100% 通过不代表用户体验好
4. **产物必须落盘**——`docs/reports/收束报告-vX.Y.md` + Git tag `vX.Y`，后续的人能翻历史

**AgentHub 实例化映射**：阶段 1 → `scripts/check_docs.py`（命名校）+ `skills/doc-sync/`（归档）；阶段 2 → `scripts/verify.bat`（ruff + pytest cov + tsc + eslint）+ 全量 `pytest -q`；阶段 3 → `skills/code-review/`（按 conventions 01-08 红线逐条）+ 人审签核；阶段 4 → `docs/specs/05-testing-strategy` E2E 5 条 Core User Stories + Playwright 录制；收束关闭 → 报告落盘 + STATUS 收束行 + `git tag vX.Y`。

**反面案例**（plan_bcf9945c 集成验证）：Inbox 视觉收 3 重 gap（backend TODO + frontend mock + 无 nav）→ 4 次 retry 失败 → owner **不盲目第 5 次 retry**，而是**降级验证层级**（visual → API+code）并主动记 known gap → ADR-0010 立方法论「下次遇到 P0 范围外的项不再硬 retry」。详见 §f。

---

## f. 截图引用：dashboard.html + MCP F1 收束过程

### dashboard.html（协作可视化）

- **入口**：`start.bat` → `python scripts/start_server.py` → http://localhost:8000/dashboard.html
- **风格**：暖色 Claude 风（焦糖色 + Songti SC 衬线），米色背景
- **数据源**：`STATUS.md`（一行 = 一位成员；每周更新「正在做 / 阻塞 / 完成了什么」）
- **Tab**：进度（按人表格 + Git 映射）/ ADR 列表 / 收束报告 / 图谱（嵌入 `.understand-anything/graph.html`）
- **关键作用**：① demoscene 可读（3 秒看全项目状态）；② 跨人交接（分布式协作看板）；③ 审计入口（图谱 Tab 直接看 `.codegraph/graph.json`）

### MCP F1 收束过程（4 阶段真实案例）

**触发**：`worklogs/decisions/0001-cli-first-pivot.md` 决策路径 → F1「市场 + 安装」5 端点全实现（commit `3c0027c`..`f59a45a`）。完整报告：[`docs/reports/收束报告-MCP-F1.md`](reports/收束报告-MCP-F1.md)（140 行）。

| 阶段 | 关键发现 / 决策 |
|------|----------------|
| **1 整理** | ruff All checks passed；worklog `worklogs/袁/2026-06-03_MCP-P1核心链路+二次对账.md` 齐全；**关键决策 → 提升 ADR-04**（二次对账 10 项 R1-R10 + 安装探针架构） |
| **2 测试** | MCP 专项 19/19 通过（三路径覆盖：rules / market / install / uninstall / 路由注册）；全量 2 失败为 Windows 无 `pi-agent` CLI 环境项，权威跑测在 Docker |
| **3 审计** | **AI 线**：AR-01 5 层洋葱（domain/mcp 零 sqlalchemy/fastapi 依赖）✅ / CR-01/10/11 零 print/密钥/注释码 ✅ / AP-01 URL kebab ✅ / T-03 三路径 ✅；2 项 🟡 defer（AP-02/AP-05）已立 ADR；**人线**：袁签核通过 |
| **4 验证** | §2.6 PR-01 冻结草案契约回演 5 端点全通过；用户故事「workspace 浏览 MCP 市场 → 安装到工作区」后端闭环；无 UI（前端 P3） |
| **关闭** | Git tag `mcp-f1` 打在 `9d7cdf2` → 并入 main；袁授予直接合并权（单人项目） |

**双线合入结论**：AI 线无 🔴 红线 + 人线通过 = **收束-1 闭合（2026-06-03）**，进入 P2（F2 绑定 + `attach_mcp`）。F1 闭合 24h 内 F2 启动（commit `9ff77be` → `002f3fb`），收束-2 双线签核见 [`docs/reports/收束报告-MCP-F2.md`](reports/收束报告-MCP-F2.md)。

---

## 引用清单（飞书文档超链接同步）

- **主规格**：[`docs/plan/PRD_AgentHub_统一方案.md`](plan/PRD_AgentHub_统一方案.md) v4.0
- **协作流程**：[`docs/conventions/ai-workflow_AI协作开发流程/`](conventions/ai-workflow_AI协作开发流程/)（01-07 共 7 篇）
- **STATUS**：[`STATUS.md`](STATUS.md) · **dashboard**：[`dashboard.html`](dashboard.html)
- **MCP 收束报告**：[`docs/reports/收束报告-MCP-F1.md`](reports/收束报告-MCP-F1.md) · [`docs/reports/收束报告-MCP-F2.md`](reports/收束报告-MCP-F2.md)
- **集成验证 + 4 张真集成截图**：[`docs/deliverables/integration-verify-report.md`](deliverables/integration-verify-report.md) + `docs/deliverables/screenshots/integration-{01..04}.png`
