# AgentHub 开发路线图

> 版本: v2.0 | 基于 PRD v4 §里程碑

---

## 一、总览（20 天）

```
M1(5/20-22)  M2(5/23-27)  M3(5/28-6/1)  M4(6/2-5)  M5(6/6-9)  M6(6/10)
███████████  █████████████  █████████████  ██████████  ██████████  ██
环境+验证     单聊MVP        群聊+协调者     产物预览     文档+打磨    提交
```

| 里程碑 | 日期 | 交付标准 | 成功闸门 |
|--------|------|---------|---------|
| **M1** | 5/20-22 | API 环境就绪、适配器框架、前后端脚手架 | 调通至少 1 个 Agent 系统 API |
| **M2** | 5/23-27 | 对话列表 + 1v1 聊天 + 流式 + 代码块渲染 | "需求→代码→预览"闭环可走通 |
| **M3** | 5/28-6/1 | 群聊创建 + @协调者/自动检测 + 任务拆解 + DAG 编译 + 并行调度 | 复杂任务自动拆解到 ≥2 Agent |
| **M4** | 6/2-5 | 网页预览卡片 + Diff 视图 + Pin + 自建 Agent（选系统+配模型） | 聊天流中预览、修改、确认产物 |
| **M5** | 6/6-9 | PRD 终稿 + 架构文档 + SPEC/Skill/Rules 沉淀 + 3min Demo | 5 个 Core User Stories 覆盖 |
| **M6** | 6/10 | 代码仓库整理、README 完善、最终提交 | 材料送达 |

---

## 二、M1 — 环境搭建 + 技术验证（5/20-22）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|---------|
| 1.1 | 项目脚手架：FastAPI + React + Vite + Docker Compose | 4h | `docker compose up` 前后端通信 |
| 1.2 | PostgreSQL + Redis + Alembic 初始 migration | 4h | 6 张表可创建/回滚 |
| 1.3 | ClaudeAdapter 框架（调用 Claude Code CLI）+ 流式适配 | 8h | 发送 prompt → 收到流式响应 |
| 1.4 | CodexAdapter 框架 | 4h | 同上 |
| 1.5 | TraeAdapter 框架 | 4h | 同上 |
| 1.6 | Agent CRUD API (POST/GET/PATCH/DELETE /api/agents) | 4h | Swagger 可测 |

**M1 出口**: 能通过 API 创建 Agent（选系统+配模型），至少一个 Adapter 调通。

---

## 三、M2 — 单聊 MVP（5/23-27）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|---------|
| 2.1 | WebSocket 实时通信 + 心跳/重连 | 6h | 双向消息延迟 < 500ms |
| 2.2 | Session + Message CRUD | 4h | 创建会话、发消息、查历史 |
| 2.3 | 流式输出：SSE → WS → StreamingText 组件 | 6h | 逐 token 渲染 |
| 2.4 | Chat UI：会话列表 + 聊天窗口 + MessageBubble | 8h | 完整聊天体验 |
| 2.5 | 私聊模式：dispatch_mode=direct | 4h | 选 Agent → 发消息 → 流式回复 |
| 2.6 | 代码块渲染 + 基础 Diff 预览（文本模式） | 4h | 代码高亮 |

**M2 出口**: 用户能和一个 Agent 完成"需求 → 代码 → 预览"闭环。

---

## 四、M3 — 群聊 + 协调者（5/28-6/1）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|---------|
| 3.1 | Group API + 群聊 UI | 8h | 创建群组、添加成员、群聊消息 |
| 3.2 | 协调者自动创建（群组创建时）+ 成员列表系统蓝标 | 4h | 协调者可见、不可移除 |
| 3.3 | @mentions 解析 + dispatch_mode=auto 路由 | 6h | @协调者→触发 / @Agent→路由 / 无@→LLM检测 |
| 3.4 | Coordinator Agent Prompt + 任务分解 | 10h | 输入需求 → 输出结构化 TaskPlan JSON |
| 3.5 | Harness: DAG 编译 + 环检测 + asyncio.gather 并发 | 8h | TaskPlan → asyncio.gather 并发执行 |
| 3.6 | 多 Agent 并行执行 + 结果合并 | 8h | 两个 Agent 并行产出 → 群聊分别展示 |
| 3.7 | Task FSM + Guard Functions + tasks.status 状态字段 | 6h | 状态转换合法，事件可追溯 |

**M3 出口**: 复杂任务自动拆解分派到 ≥2 Agent，产物在群聊中展示。

---

## 五、M4 — 产物预览 + 迭代（6/2-5）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|---------|
| 4.1 | Diff 预览：diff2html 内联卡片 | 8h | 绿色/红色标注增删行 |
| 4.2 | 网页预览：iframe sandbox 卡片 | 6h | 点击预览 → iframe 渲染 |
| 4.3 | 自建 Agent（选系统→配模型→填信息）+ 对话式创建 | 8h | 表单式+对话式均可创建 |
| 4.4 | Agent 详情页（概览/能力/记忆/任务/活动/设置 Tab） | 6h | 6个Tab内容正确 |
| 4.5 | Pin 消息 + 上下文三层体系 | 4h | Pin后跨会话可见 |
| 4.6 | 收件箱 + 审批流（APPROVE/REJECT/EDIT/RESPOND） | 8h | 审批→Agent继续/取消 |

**M4 出口**: 用户在聊天流中预览、修改、确认产物。

---

## 六、M5 — 文档 + 打磨（6/6-9）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|---------|
| 5.1 | UI/UX 优化（主题、响应式、动画） | 8h | 交互流畅 |
| 5.2 | 任务看板（列表/看板视图 + 筛选） | 8h | 聊天派发的任务在看板中可见 |
| 5.3 | Token 消耗监控 | 4h | 实时显示 |
| 5.4 | E2E 测试（Playwright 覆盖 5 个 Story） | 8h | 全绿 |
| 5.5 | 文档终稿（PRD + 架构 + SPEC + Rules） | 8h | 完整 |
| 5.6 | 3min Demo 视频 | 8h | 覆盖 5 个 Core User Stories |

---

## 七、降级策略

| 阻塞 | 降级 |
|------|------|
| Agent 系统 API 接入阻塞 | Mock Agent 返回预设响应，保证 UI 完整 |
| 协调者任务拆解不稳定 | 降级为手动 @Agent 模式 |
| 内联预览阻塞 | 新窗口打开预览 |
| LLM Provider 不可用 | 切换备选 Provider；全部不可用→Mock 演示 |

---

## 八、MVP 收尾冲刺（M5+：6/2-6/9）

> 来源：`docs/plan/后续升级计划/后续计划.txt`（v1.0 补充稿，2026-06-01）
> 目标：保答辩 3min Demo 跑通；不超出 MVP 时间盒的功能全部砍掉。

### 8.1 必修（P0，6/2-6/5 必做，约 28h）

| # | 任务 | 工时 | 验收标准 | 状态 | 关联 |
|---|------|------|---------|------|------|
| P0-1 | 网页预览 iframe 卡片内联到消息流 | 8h | 聊天流中点开 Agent 返回的 URL → sandbox iframe 渲染 | ⬜ 待办 | 课题 4 |
| P0-2 | Diff 视图（diff2html 集成） | 6h | 增删行绿/红标注，可点开全屏 | ⬜ 待办 | 课题 4 |
| P0-3 | 文件附件上传 + 预览 API | 6h | multipart 端点 + 消息中可下载/预览 | ⬜ 待办 | 课题 1 |
| P0-4 | Pin 消息 UI（复用 context_builder 三层体系）| 3h | Pin 后跨会话可见，状态可见 | ⬜ 待办 | 课题 1 |
| P0-5 | 复制代码 / 重新生成按钮 | 2h | MessageBubble 操作区可见 | ⬜ 待办 | 课题 1 |
| P0-6 | 端到端 Demo 数据集 + 录制脚本 | 3h | 5 个 Core User Story 跑通 | ⬜ 待办 | 课题 交付物 |

### 8.2 加分（P1，时间允许，6/6-6/8，约 15h）

| # | 任务 | 工时 | 验收标准 | 状态 | 关联 |
|---|------|------|---------|------|------|
| P1-1 | 工作目录 UI 落地（后端 0005 migration 已有）| 4h | Agent 详情页可切换工作目录 | ⬜ 待办 | 创新 10% |
| P1-2 | Token 消耗监控（聊天/任务双视图）| 3h | 实时显示单 Agent / 单会话消耗 | ⬜ 待办 | 工程深度 |
| P1-3 | CLI PATH 扫描前端实时展示 | 2h | 启动时自动扫，结果 UI 可视化 | ⬜ 待办 | 创新 10% |
| P1-4 | Playwright E2E 覆盖 5 个 Story | 6h | 全绿，可作 CI gate | ⬜ 待办 | T-01~06 |

### 8.3 MVP 不做（P2/P3，超出时间盒）

| 项 | 课题 | 原因 |
|----|------|------|
| 一键生成预览 URL / 静态站点 / 容器化部署 | 5 | P2 |
| 桌面端（Electron / Tauri）| 6 | P2 |
| 移动端（轻量 H5）| 6 | P2 |
| PPT 预览（.pptx 渲染）| 4 | P2 |
| Diff 版本历史 | 4 创新 | P3 |
| 多 Provider 智能路由（成本/速度/质量）| 4 创新 | P3 |
| Agent 工作记忆长期持久化 | 4 创新 | P3 |

### 8.4 Demo 视频脚本（3min）

| 时段 | 内容 | 关联 Story |
|------|------|-----------|
| 0:00-0:15 | 开场："4 CLI 适配器 + CLI×Provider 矩阵" | 创新点 |
| 0:15-0:45 | S1 新建会话 → 1v1 流式 → 代码块 | Story 1 |
| 0:45-1:15 | S2 群聊 → @协调者 → 多 Agent 并行 | Story 2 |
| 1:15-1:45 | S3 产物内联预览（网页/Diff 卡片）| Story 3 + P0-1/P0-2 |
| 1:45-2:15 | S4 自建 Agent：对话式 + 表单式 + 矩阵 | Story 4 |
| 2:15-2:45 | S5 Inbox 审批 + 任务看板 | Story 5 |
| 2:45-3:00 | 收尾：规范/SPEC/ADR/22 单元 + 创新点 | 考察 30% |

### 8.5 风险与降级

| 风险 | 触发条件 | 降级方案 |
|------|---------|---------|
| P0-1 iframe 不稳 | 沙箱权限 / X-Frame-Options | 降级"新窗口打开预览" |
| P0-2 diff 解析异常 | 编码 / 大文件 | 退化为纯文本 diff |
| 多 Agent 协调超时 | 任务 > 30s | 手动 @Agent 单步走 |
| LLM Provider 不可用 | 全部 401/超时 | Mock 适配器保 UI 完整 |
| Demo 录制当天环境挂 | 任意 | 预备录屏备份（提前一周录制一次）|

---

## 九、变更记录

| 日期 | 变更 | 来源 |
|------|------|------|
| 2026-05-XX | 初版 M1-M6 路线图 | PRD v4 |
| 2026-06-01 | §八 新增 MVP 收尾冲刺（基于 `docs/plan/后续升级计划/后续计划.txt` v1.0）| 后续计划补充稿 |
| 2026-06-02 | §十 新增 **MCP 功能 v1**（P1→P3→P2→P4，4 阶段 13 天 + 严格收束）| `docs/plan/MCP功能PRD.md` v1.0 + `MCP功能计划_v0.md` v0.2 |

---

## 十、MCP 功能 v1（6/2-6/15，4 阶段 13 天）

> **单一权威入口**：[`docs/plan/后续升级计划/MCP接入/README-REVISION.md`](后续升级计划/MCP接入/README-REVISION.md)（**2026-06-03 修订版**，按可行性清单 12 项问题重写）
>
> 详情（已合并去重）：`README-REVISION.md` §0-3 速览 + 6 份关键文档（FS/SA/TA/MD/IC/MCP-UI-frontend）+ 08/closure-verdict 双口径
> 范围: F1 MCP 市场 / F2 Agent 接入 / F3 创建 MCP / F5 工具调用展示（全量 + 工具展示）
> 顺序: P1(6/2-6/5) → P3(6/6-6/8) → P2(6/9-6/11) → P4(6/12-6/15)
> 收束: 严格 4 阶段硬闸门（整理/测试/审计/验证）+ ADR + 收束报告
> 数据: 4 张表 = 3 实体（`mcp_servers` / `workspace_mcp_installations` / `agent_mcp_bindings`）+ 1 日志表（`mcp_tool_call_logs`）
> API: 8 个 HTTP 端点 + 2 个 WS 事件 →（🔒 PR-01 冻结草案已落 `docs/specs/04-commands_命令接口.md` §2.6 + §三，**待 2 人 Review**；URL 前缀 `/api/mcp/`，AP-05 暂缓见 [ADR-0003](../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)）
> 前端: 3 个新页（`/mcp-market` 列表/详情 + `/mcp-create`）+ 1 个 Tab（Agent「MCP 接入」）+ 1 store + 6 组件
> 工时: 159h 总（52 + 34 + 40 + 33）
>
> **修订版 4 项决策**（V1.3.1 errata）：
> 1. 单一权威 = 修订版 `MCP接入/`（合并 §十 工程口径）
> 2. 安装表名 = `workspace_mcp_installations`（E-01）
> 3. dry-run = 单 Docker + compose 资源限额（E-03 简化版）
> 4. SDK Adapter（F-013）= 移下期，CLI Adapter 预留 `attach_mcp(...)` 扩展点
>
> **代码空间状态**（2026-06-03 更新）：后端 P1 核心链路已落地（domain/mcp 4 文件 + repo 接口/实现 + models 4 表 + alembic 0006-0009 + 2 service + api/routers/mcp.py 3 端点 + schemas/mcp.py + get_current_user JWT 解析）；12 单测绿（rules/market/install 三路径）。前端 0/11 待 P3。
>
> **二次对账（2026-06-03，README-REVISION §9）**：P1 启动前逐文件复核 plan→code，发现首轮 review 漏掉的实体级不存在引用 R1-R10（无 workspaces/users 表、零 JWT 强制、trace_id 零设施、WS 信封不符、错误体 {detail} 非 AP-02、SQLite 强制可移植类型），并修复 `.gitignore` 裸 `backend/` 误伤源码树致新增文件被忽略的阻断 bug。落地口径：workspace_id 暂存 session_id 裸 Uuid；created_by/installed_by 裸 Uuid 存 JWT sub；可移植类型；错误体沿用 {detail}。
>
> **P0 计划整理 + PR-01 草案（2026-06-03 完成）**：核验修订版属实 + 校正 §3 路径漂移 + PR-01 端点冻结草案落 04-commands §2.6/§三 + 原计划残留归档（445+22+3 文件）+ ADR-0003。**P1 启动前置门：04-commands §2.6 经 2 人 Review Approve（PR-01/PR-06）→ 确认 PR-09 spec 同步 → 才能写 alembic 0006。**

---

### ▶ 接手指引（给下一个 AI 会话 / 代码开发起点）

> 计划已整理完毕（2026-06-03，docs-only，commit `2025d42`，分支 `feature/mcp/pr01-freeze-and-plan-cleanup`，**未 push**）。下一会话做**代码开发**，从这里开始。

**第 0 步——过 PR-01 闸门（写代码前的红线，不可跳）**
- `docs/specs/04-commands_命令接口.md` §2.6（8 端点）+ §三（4 WS 事件）目前是 🔒 **冻结草案**，**需 2 人 Review Approve** 才算冻结（PR-01/PR-06）。未过闸禁止写后端实现。

**落地权威三件套（照这三处写，次级文档正文有旧路径已加 ERRATA 横幅，勿照抄）**
1. 文件结构 → `docs/plan/后续升级计划/MCP接入/06-详细设计/FS-MCP-V1.0-20260602.md` §1（真实落点树）
2. 接口契约 → `docs/specs/04-commands_命令接口.md` §2.6 + §三
3. 架构 / 数据 → `docs/specs/01-architecture_架构定义.md` §MCP + `docs/specs/03-data-model_数据模型.md` §MCP

**关键落地约定（已校正为真实代码树）**
- URL 前缀 `/api/mcp/`（**无 `/v1/`**，对齐现有 `/api/agents`，依据 [ADR-0003](../../worklogs/decisions/0003-mcp-url-prefix-and-ap05-deferral.md)）
- 路由文件 `api/routers/mcp.py`，`APIRouter(prefix="/api/mcp")`；WS `api/ws/toolcall.py`
- 4 张表**追加进单文件** `infrastructure/db/models.py`（不新建 `models/` 包）+ alembic `0006`（续 0001-0005）
- 领域子包 `domain/mcp/{mcp_server,mcp_installation,mcp_binding,rules}.py`
- 编排服务**扁平** `application/services/mcp_{market,install,binding,create}_service.py`（不建 `application/mcp/` 子包）
- `attach_mcp(...)` 抽象方法加在 `domain/llm/protocol.py::AgentRuntime`，由 `infrastructure/llm/{claude_code,opencode,pi_agent}_runtime.py` 实现（AR-02：只扩展 Adapter，不另起运行时）
- dry-run 简化版 → `infrastructure/mcp/dry_run.py`（单 Docker + compose 限额，非多 OS 沙箱）

**P1 第一步动作**（闸门过后）：PR-09 确认 spec 同步 → 写 alembic 0006 + `infrastructure/db/models.py` 追加 4 表 → 3 端点（list/detail/install）。

---

| 阶段 | 日期 | 范围 | 工时 | 收束 | 状态 |
|------|------|------|------|------|------|
| P0 整理+PR-01草案 | 6/3 | 路径校正 + 端点冻结草案 + 归档 + ADR-0003 | — | — | ✅ 完成（§2.6 Reviewer Approve） |
| P0.5 二次对账 | 6/3 | schema↔代码审计 R1-R10 + spec 修订 + .gitignore 修正 | — | — | ✅ 完成（见 README-REVISION §9） |
| P1 F1 市场 | 6/2-6/5 | 数据层(4 表/迁移/实体)+ 5 端点 ✅；安装探针 McpInstaller 端口 + LocalMcpInstaller 结构校验(transport 必填项，422 拦截非法配置)✅；真实可达性/进程探针 ⬜（P2/P3 seam） | 52h | ✅ ADR-04 + [收束报告](../reports/收束报告-MCP-F1.md) | ✅ F1 齐+19 测试绿；收束-1 ✅ 闭合（双线签核）→ 并入 main |
| P3 F3 创建 | 6/6-6/8 | stdio/sse 提交 + 模板 + dry-run 验证 | 34h | 收束 3 + ADR 0005 | ⬜ 待办 |
| P2 F2 接入 | 6/9-6/11 | bind/unbind 端点 + 请求携带 attach（ADR-05）+ claude_code 注入 + rebind 修复(0010) ✅；opencode/pi_agent 注入增量 ⬜ | 40h | 收束 2 + ADR-05/06 | 🔄 进行中（核心 attach 通 + 26 测试绿） |
| P4 F5 展示 | 6/12-6/15 | 工具调用内联卡片 + WebSocket 事件 | 33h | 收束 4 + ADR 0007 | ⬜ 待办 |
