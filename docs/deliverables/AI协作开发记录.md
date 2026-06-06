# AgentHub AI 协作开发记录

> 项目：AgentHub — IM 聊天式多 Agent 协作平台 · 周期：2026-05-20 → 2026-06-07（M1→M5 收尾冲刺）
> 仓库：GitHub `oldmanpushbike/agenthub`（feature 分支并入 main）
> 本文档定位：交付物 3「AI 协作开发记录」——飞书文档同步介绍协作流程与产物

---

## a. 团队介绍

AgentHub 由 **3 位人类开发者 + 1 位 Claude Agent** 共同完成，遵循「Opus 开发 + DeepSeek 审查 + 人决策」的角色分工（[`01-角色分工与文件体系.md`](../conventions/ai-workflow_AI协作开发流程/01-角色分工与文件体系.md)）。具体角色与职责划分如下：

- **董**（git: yii.d）——协调者 + 域 2 DRI（域 2 = 协调/编排/Memory）。任务编排、记忆系统 B 方向设计与实现、CLI 多模型代理打通、群聊编排（含 Coordinator 分解 + asyncio.gather 并发）、`MCP save_memory` 端到端打通、前端记忆面板、群聊全栈实现。
- **黎**（git: oldmanpushbike）——全栈 + 域 3 DRI（域 3 = 工具链/桌面）。39 commits 合并、ProviderKeyResolver、OpenCode 集成、CLI PATH 扫描、桌面 App 选型（Tauri 2 + 瘦客户端，详见 ADR-07），M2 落地工作量 5-7 周。
- **袁**（git: xiangbianpangde）——规范架构 + MCP DRI。模板重构、全栈目录整合、MCP 计划/PRD/收束报告 F1+F2、集成验证（5/6 PASS）、roadmap 维护、Status 同步。
- **Claude Agent**（Opus 模型）——架构师 + 开发者。负责架构设计、计划审查、TDD 自检、写代码、修 bug、生成文档。git identity 自动归到「袁」目录（避免身份污染 3 人协作命名空间）。

**协作心法**：Claude 不自审自己的代码——TDD 是自检手段（保证「按预期运行」），DeepSeek 是独立审查关卡（发现「视角盲区」）。人只在审查者标记的差异点和高风险项上做决策，不做逐行审查，避免 AI 视角漂移而无察觉。

---

## b. 工作流：CLAUDE.md → conventions → specs → worklogs → STATUS → dashboard

协作流程是一条**自上而下、可追溯、可视化**的链路，每一步都有明确产出：

1. **CLAUDE.md 冷启动契约** — 每个新会话自动加载根目录的 `CLAUDE.md`，从 `git config user.name` 自动判断「你是谁」，加载对应 worklog 目录、当前进度、阻塞项、依赖说明。无须人类口头交代上下文。**产出**：会话起来就有完整背景，省 30 分钟「昨天到哪了」沟通。
2. **docs/conventions/（01-10 规范）** — AI 红线速查表：`AR-01 5 层洋葱 / CR-12 禁同步阻塞 / PR-02 feature 分支命名 / AP-02 错误信封 / T-01 独立测试 / D-05 文档命名` 等。每条红线都对应一个验证方法（grep 模式 / linter 规则 / pre-commit hook）。**产出**：所有 PR 提交前自动校验，避免「事后修规范债」。
3. **docs/specs/（00-05 + domains/）** — BDD 验收契约。每个功能点对应 API 冻结（`04-commands`）、数据模型（`03-data-model`）、5 条 Core User Stories（`05-testing-strategy`）。代码必须能让 BDD 跑通才认为「实现」完成。**产出**：每个 PR 都有明确「完成」定义。
4. **worklogs/{人名}/YYYY-MM-DD_*.md** — 「给下一位的交接」。每份末尾固定 `## 给下一位的交接` 段：今天做完了什么、未做的是什么、需要谁配合、哪里容易踩坑。让接手的人 2 小时内能继续。**产出**：分布式协作不丢上下文。
5. **STATUS.md** — 进度数据源（自己的行 + 交接段 + 技术债段）。**产出**：3 人协同一张表，谁做什么、谁阻塞、什么债全可见。
6. **dashboard.html** — 物理可观测层。`scripts/check_worklog.py` 校验 STATUS 与 git log 一致；dashboard 暖色 Claude 风（焦糖色 `#cc785c` + Songti SC 衬线）渲染进度图。**产出**：demoscene 可读（3 秒看全项目状态），跨人交接看板。

---

## c. ADR 索引（10 份架构决策记录）

`worklogs/decisions/` 是 AgentHub 的「决策记忆」——记录**为什么选 A 不选 B**、当时选项、权衡依据、未来影响。仅在收束节点从 worklog「关键决策」段提升，避免「边写代码边造 ADR」的失序。

**核心 10 份**（按时间顺序，每份含「背景 / 选项 / 决策 / 后果」四段）：

1. **0001 CLI 优先**（[链接](../worklogs/decisions/0001-cli-first-pivot.md)）— API 模式自建 Harness 需 95h+（Tool Loop + Tool 沙箱 + HITL + 会话状态 + Worker Pool + 多模型路由），M2 6 天窗口不可行。CLI 模式（Claude Code 自带 tool/state/Permission）<300 行 + SessionStore（Redis 7d TTL）即可跑通。决策：**CLI 优先 + 双轨保留**，API 模式留 M3+。
2. **0002 Phase 1 长驻 CLI**（[链接](../worklogs/decisions/0002-phase1-long-running-cli.md)）— V0 模式 `spawn → stdin.write(prompt) → write_eof() → exit` 每次新建进程无记忆。V1 改造为 `spawn(--input-format stream-json) → 持续 stdin JSONL → 长驻`。灰度开关 `CLAUDE_CODE_LONG_RUNNING=1` 默认关。决策：**长驻 + stream-json**，对外 `stream()` 契约不变。
3. **0003 MCP URL = `/api/mcp`**（[链接](../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)）— AP-05 要求 `/api/v1/...`，但全库现状无 `/v1/`。MCP 单点加 v1 会制造不一致。决策：**对齐现状 `/api/mcp/` + AP-05 暂缓进 NB-02**。附则：记忆 MCP 协议端 mount 移到 `/api/mcp-memory`（避免 mount 遮蔽 REST 子路径）。
4. **0004 MCP F1 二次对账**（[链接](../worklogs/decisions/0004-mcp-f1-landing-and-installer-seam.md)）— 计划写「FK→workspaces」实无该表（实际 workspace = `sessions.workspace_path` 字符串）。决策：**裸 UUID stand-in**（`workspace_id = session_id`、`created_by = JWT sub`），仅对真实表加 FK。安装=结构校验探针（422 拦截非法配置）而非拉起进程。
5. **0005 attach = 请求携带**（[链接](../worklogs/decisions/0005-mcp-attach-request-carried.md)）— 原计划 `AgentRuntime.attach_mcp(bindings)` 存实例状态，但 runtime 是池化/进程级共享，存实例状态会跨 agent 串号。决策：**请求携带 `AgentRequest.mcp_servers`**（无状态、零串号），runtime 在 build_cmd 时读 + 写 .mcp.json。
6. **0006 MCP 注入逐调用隔离通道**（[链接](../worklogs/decisions/0006-mcp-injection-per-runtime-isolated-channel.md)）— 隔离通道优先级：① 逐调用 flag（claude_code `--mcp-config <tmp>`） ② env 指向临时配置（opencode `OPENCODE_CONFIG=<tmp>`） ③ 逐 workspace 项目配置。**禁止全局/共享配置 mutation**。opencode 据此拉回本期，pi_agent 本机无 pi 二进制保留 deferred。
7. **0007 Tauri 2 桌面 App 转向**（[链接](../worklogs/decisions/0007-tauri-desktop-pivot.md)）— 5 路径对比（Capacitor / Tauri 2 / RN / Flutter / PWA+TWA）。决策：**Tauri 2 + 瘦客户端（M2）+ GitHub Releases**，不进任何商店。包体 3-5MB vs Electron 100MB+。
8. **0008 owner 自决授权**（[链接](../worklogs/decisions/0008-self-governance-authorization.md)）— 用户明早未到岗期间，owner 可自主做判断（verifier FAIL retry / 范围微调 / worker steer / 降级方案 / 临时改 prompt / git commit + push），但**不可删用户文件 / 不可 force push main / 不可 reset --hard**。每个重大决定必须落 `0009+NNN-<slug>.md`。
9. **0009 P2 兜底 cron**（[链接](../worklogs/decisions/0009-p2-handoff-cron.md)）— 2026-06-07 10:00 用户未报备 → cron `p2-handoff-watch` 自动启动 P2 接力（MCP P3 F3 创建 / P4 F5 展示）。沿用 0008 自决授权 + 上下文清理规则。
10. **0010 集成验证 E downscope**（[链接](../worklogs/decisions/0010-integration-verify-downscope.md)）— Inbox 视觉 M4 TODO（不在 P0 范围）。4 次 retry 失败后，**不盲目第 5 次 retry**，而是降级验证层级（visual → API+code）并主动记 known gap。决策：5/6 PASS override_accept，video-record 用 S2 group 真 backend 渲染。

**方法论固化**（ADR-04/06 沉淀）：凡「N 个组件都能做 X」必须逐个打开验证 X 在每个组件里可行——避免 R11「opencode 也能注入 MCP」未经实测断言。ADR-06 据此实测发现 opencode 的 `OPENCODE_CONFIG` env 才是逐调用隔离通道（不是写全局），R11 的「写全局会串号」根因不成立 → opencode 拉回本期。此方法论在 F2 实现期间避免了一次「想当然引入全 runtime 支持」的返工。

---

## d. worklogs 目录结构 + 模板

**目录布局**（`worklogs/{Git 用户名 → 中文名}/`）：

```
worklogs/
├── template.md                              # 通用模板（交接段是核心）
├── decisions/                                # ADR 仓库（0001-0010 共 10 份）
├── 董/                                       # git config user.name = yii.d
├── 黎/                                       # git config user.name = oldmanpushbike
└── 袁/                                       # git config user.name = xiangbianpangde
```

**命名规范**（D-05 文档规范）：`YYYY-MM-DD_<一句话简短描述>.md`；禁止 v1/v2 序号、重复描述、空标题。描述用「名词+动词」结构（如「MCP-P1 核心链路+二次对账」而非「MCP 进度更新 v2」），便于 grep 检索。

**Git ↔ 人名映射**（`STATUS.md` 「Git ↔ 目录映射」段 + `scripts/check_worklog.py` 自动校验）：

| Git 用户名 | 日志目录 |
|-----------|----------|
| oldmanpushbike | 黎 |
| yii.d | 董 |
| xiangbianpangde | 袁 |

**worklog 模板核心段**（`worklogs/template.md`）：固定 6 段，缺一即视为「日志不合格」：

- `## 目标` — 一句话：今天要做什么
- `## 产出` — commit hash 列表 + 文件清单 + 验证结果（测试通过 / 手动验证 / 截图）
- `## 关键决策` — 表格：决策 / 原因 / 影响 → 收束节点评审是否提升 ADR
- `## 未完成 / 阻塞` — 待做项 + 阻塞原因 + 谁解锁
- `## 给下一位的交接` — 接手的人 2 小时内能继续：下一步该做什么、哪里容易踩坑、临时约定、需要谁配合
- （可选）`## 截图 / 录屏 / curl 输出` — 视觉/接口证据

**填充示例**（`worklogs/袁/2026-06-03_MCP-P1核心链路+二次对账.md` 摘录）：

```markdown
## 目标
跑通 MCP P1 核心链路（domain/mcp 5 实体 + alembic 0006-0009 + market/install service + 3 端点 + 单测三路径）

## 产出
- commit `f59a45a` — feat(mcp): domain/mcp 4 实体 + rules + repo 接口
- commit `xxxxxxx` — feat(mcp): alembic 0006-0009 (4 表 + 可移植类型)
- commit `xxxxxxx` — feat(mcp): api/routers/mcp.py 3 端点
- 测试：tests/test_mcp.py 19/19 通过（rules / market / install / uninstall / 路由注册）

## 关键决策
| 决策 | 原因 | 影响 |
|------|------|------|
| workspace_id = 裸 UUID stand-in（实存 session_id） | 现状无 workspaces 表，FK 不可行 | 收束节点评审时考虑进 ADR |
| 安装 = 结构校验（422 拦截） | CLI 不在后端长驻，无需拉起进程探针 | P3 真实可达性留给 seam |

## 给下一位的交接
- P2 起点：ADR-05 已冻结 `AgentRequest.mcp_servers` 路径，下一会话直接 `McpBindingService.build_request_mcp_servers(agent_id)`
- 坑：`agent_mcp_bindings` UNIQUE(agent,installation) 与软删 rebind 冲突，P2 绑定前需 alembic 改部分唯一
```

**`scripts/check_worklog.py` 自动化检查**（pre-commit hook 触发）：push 时校验「我今天 commit 了 → 我今天的 worklog 必须存在」——避免「代码上线了日志没写」丢历史。校验失败 = 阻止 push，强制写日志。

---

## e. 收束报告 4 阶段方法论（整理 / 测试 / 审计 / 验证）

**强制流程**——跳过 = 后续功能点不通过。AI 不自动启动收束，但 AI **会拦住**越过闸门的开发（[`06-第三步_收束节点.md`](../conventions/ai-workflow_AI协作开发流程/06-第三步_收束节点.md)）。

```
收束节点 = 质量闸门（每 3 个功能点或版本变更触发）
阶段1 整理 ──→ 阶段2 测试 ──→ 阶段3 审计 ──→ 阶段4 验证
 代码/文件    全量+集成+回归   AI+人双线    BDD+用户故事
```

**阶段 1 整理**：消除本批次熵增。
- 代码：ruff 清未用 import / 删注释代码（除 TODO/FIXME/HACK）/ 删遗留 `print()` `console.log()` / 识别孤儿模块 → 人工确认合并 / 检查依赖黑洞
- 文件：`worklogs/` 齐全（每个功能点 1 份）/ 过时文档归档 `archive/` / CLAUDE.md 模块图谱更新 / FILE_GRAPH.md 同步 / 僵尸分支 `git branch --merged` 清理
- **决策整理**：回顾本批次 worklog「关键决策」段，判断哪些值得提升为 ADR → 写入 `worklogs/decisions/`

**阶段 2 测试**：CI 增量不做的全量。
- 全量单测：`pytest` / `npm test` 100% 通过
- 全量集成 + 跨模块回归：本批次涉及模块 + 间接依赖方（按调用图影响分析）
- 手工探索性：核心用户流程 3-5 条（不靠脚本，按「用户会怎么用」随机路径操作）
- 性能基准：vs 上收束节点的关键 API / 页面加载 P95，>20% 退化即标记

**阶段 3 审计**（AI + 人双线，互不替代）：
- **AI 线**（全量模式扫描，**不判断对错，只标记疑点**）：
  - 架构红线：循环依赖（AR-01 5 层） / 跨层调用 / 领域层依赖框架 / 敏感信息硬编码
  - 代码红线：裸 `print()` / 裸 SQL 拼接 / 密钥硬编码 / 注释代码块 / 遗留调试代码
  - Git 规范：main 直接 push（🔴） / commit 格式（Conventional Commits）/ 僵尸分支
  - API 规范：错误码一致性 / 废弃接口 `@deprecated` / 版本管理（破坏性变更升主版本）
  - 测试规范：覆盖率下降 / Flaky test / 未测试的 public API
  - 图谱缺陷：08-code-understanding §3.3 缺陷检测模式库（循环依赖、未使用函数、上帝类、未处理异常、跨层违规）
- **人线**（聚焦 AI 不擅长的领域）：
  - AI 标记项复核：逐条确认 🔴 红线违规是否真是问题
  - 业务逻辑合理性：互相矛盾的地方？「为了通过测试而写代码」？
  - 设计意图偏离：实现是否偏离 `docs/plan/背景.md` 和对应 BDD 的原始设计意图？偏离须补 ADR
  - PR/CR 流程抽查：描述完整 / Review 实质反馈 / 合入前通过 CI / 无「自己 Approve 自己」
  - 主观质量：新代码命名能否让团队其他人一眼看懂？结构是否合理（2 小时内能接手）？
- **双线合入**：🔴 红线必修 / 🟡 中风险接受须 ADR / AI 误报由人签核说明理由通过

**阶段 4 验证**：「做完了 ≠ 做对了」。
- BDD 场景回演：逐条对照 `docs/specs/` 中本批次功能点的 BDD 场景重新执行（不是开发时截图，是现在重新跑）
- 可视化产出复核：本批次每个功能点的截图/录屏/curl 输出在当前版本重新生成，对比开发阶段是否有退化
- 用户故事回溯：回到 `docs/plan/背景.md`「为什么做这个项目」，本批次 3 个功能点是否让你离目标更近了？如果给陌生人演示，他能理解价值吗？
- 技术债盘点：本批次的「3 分钟回顾」中记录的技术债 + 本收束节点新发现的问题 → 统一记到 `STATUS.md` 技术债区，标注发现时间、优先级、预计修复节点

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
- **风格**：暖色 Claude 风（焦糖色 `#cc785c` + Songti SC 衬线），米色 `#f5f4ee` 背景
- **数据源**：[`STATUS.md`](../STATUS.md)（一行 = 一位成员；每周更新「正在做 / 阻塞 / 完成了什么」）
- **Tab**：进度（按人表格 + Git 映射）/ ADR 列表 / 收束报告 / 图谱（嵌入 `.understand-anything/graph.html`）
- **关键作用**：① demoscene 可读（3 秒看全项目状态）；② 跨人交接（分布式协作看板）；③ 审计入口（图谱 Tab 直接看 `.codegraph/graph.json`）

### MCP F1 收束过程（4 阶段真实案例）

**触发**：[`0001-cli-first-pivot.md`](../worklogs/decisions/0001-cli-first-pivot.md) 决策路径 → F1「市场 + 安装」5 端点全实现（commit `3c0027c`..`f59a45a`）。完整报告：[`收束报告-MCP-F1.md`](../reports/收束报告-MCP-F1.md)（140 行）。

| 阶段 | 关键发现 / 决策 |
|------|----------------|
| **1 整理** | ruff All checks passed；worklog `worklogs/袁/2026-06-03_MCP-P1核心链路+二次对账.md` 齐全；**关键决策 → 提升 ADR-04**（二次对账 10 项 R1-R10 + 安装探针架构） |
| **2 测试** | MCP 专项 19/19 通过（三路径覆盖：rules / market / install / uninstall / 路由注册）；全量 2 失败为 Windows 无 `pi-agent` CLI 环境项，权威跑测在 Docker |
| **3 审计** | **AI 线**：AR-01 5 层洋葱（domain/mcp 零 sqlalchemy/fastapi 依赖）✅ / CR-01/10/11 零 print/密钥/注释码 ✅ / AP-01 URL kebab ✅ / T-03 三路径 ✅；2 项 🟡 defer（AP-02/AP-05）已立 ADR；**人线**：袁签核通过 |
| **4 验证** | §2.6 PR-01 冻结草案契约回演 5 端点全通过；用户故事「workspace 浏览 MCP 市场 → 安装到工作区」后端闭环；无 UI（前端 P3） |
| **关闭** | Git tag `mcp-f1` 打在 `9d7cdf2` → 并入 main；袁授予直接合并权（单人项目） |

**双线合入结论**：AI 线无 🔴 红线 + 人线通过 = **收束-1 闭合（2026-06-03）**，进入 P2（F2 绑定 + `attach_mcp`）。F1 闭合 24h 内 F2 启动（commit `9ff77be` → `002f3fb`），收束-2 双线签核见 [`收束报告-MCP-F2.md`](../reports/收束报告-MCP-F2.md)。

---

## 引用清单（飞书文档超链接同步）

- **主规格**：[`PRD_AgentHub_统一方案.md`](../plan/PRD_AgentHub_统一方案.md) v4.0（含 2026-06-07 增量附录：实施进度速览 + AI 协作沉淀）
- **协作流程**：[`ai-workflow_AI协作开发流程/`](../conventions/ai-workflow_AI协作开发流程/)（01-07 共 7 篇）
- **STATUS**：[`STATUS.md`](../STATUS.md) · **dashboard**：[`dashboard.html`](../dashboard.html)
- **MCP 收束报告**：[`收束报告-MCP-F1.md`](../reports/收束报告-MCP-F1.md) · [`收束报告-MCP-F2.md`](../reports/收束报告-MCP-F2.md)
- **集成验证 + 4 张真集成截图**：[`integration-verify-report.md`](integration-verify-report.md) + [`screenshots/integration-{01..04}.png`](screenshots/integration-{01..04}.png)
