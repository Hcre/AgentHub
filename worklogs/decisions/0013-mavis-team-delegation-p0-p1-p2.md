# ADR-0013: Mavis owner 创建 mavis-team 委派 — 完成 P0+P1+P2 文档沉淀 + 架构图 + ER 图 + 命令 reference

- **状态**: Accepted
- **日期**: 2026-06-07
- **决策者**: Mavis (owner, per ADR-0008 自主决策授权)
- **关联 Spec**: [docs/specs/04-commands_命令接口.md v2.2](../docs/specs/04-commands_命令接口.md) · [docs/specs/01-architecture_架构定义.md](../docs/specs/01-architecture_架构定义.md) · [docs/specs/03-data-model_数据模型.md](../docs/specs/03-data-model_数据模型.md) · [docs/plan/开发清单_roadmap.md §六 M5 5.5](../docs/plan/开发清单_roadmap.md)
- **关联 ADR**: [ADR-0008 self-governance](../worklogs/decisions/0008-self-governance-authorization.md) · [ADR-0012 BDD spec precipitation](../worklogs/decisions/0012-bdd-spec-comprehensive-precipitation.md)
- **关联 plan**: `plan_ba86c4d0` (Mavis owner 15:30 session 委派)
- **关联 worklog**: [worklogs/mavis/2026-06-07_创建团队委派.md](../worklogs/mavis/2026-06-07_创建团队委派.md)

## 背景

`plan_ba86c4d0`（Mavis owner 15:30 session）委派 docs-writer 任务：

> M5 5.5 文档沉淀收尾：roadmap §1/§6/§8.1/§8.2/§8.2.1/§8.4/§9/§▶接手指引 全对齐实际状态 + 5 层洋葱架构图 + 5 表 ER 图 + commands-reference.md + ADR + worklog。

**当前状态**（per STATUS.md 2026-06-07 15:30 + ADR-0012）：
- 04-commands §六 **17 BDD 场景已冻结**（14:26 session）+ agenthub-dev SKILL v1.0 + 05-testing §二点五 BDD+TDD
- M5 5.5 SPEC/Skill/Rules 沉淀 ✅ 但**架构图 + ER 图 + 命令 reference 三大件**仍缺
- 课题「AI 协作能力 30%」考察点 = "沉淀出和 ai 协作的 Spec、skill、rules 等协作规范"（per 背景.md line 62-64）
- 课题「代码理解度 15%」考察点 = "答辩时能否解释架构选型和核心逻辑" → 需要**可视化**辅助

**核心问题**：
- M5 5.5 SPEC/Skill/Rules 三件套已落（per ADR-0012），但**架构图、ER 图、命令 reference 三大可视化/速查**仍空缺
- **架构图 5 层洋葱**：现有仅是 01-architecture §一文字描述 + ASCII 示意（line 11-35），缺一张**答辩可用**的可视化
- **ER 图 5 主表**：03-data-model §二是 12 表 DDL 全文（v4 简化为 5+1 主表），缺**5 表关系可视化**（FK 关系 + 基数）
- **命令 reference**：04-commands §二/§三是 759 行完整契约（37 REST + 11 WS + 错误码），缺一份**快速参考表**给答辩人 / 新接手人

**ADR 编号冲突说明**：
- 原任务指令指定 ADR 编号为 `0012`，但 [ADR-0012](../worklogs/decisions/0012-bdd-spec-comprehensive-precipitation.md) 已占用（14:26 session 落档）
- per `scripts/check_docs.py` line 112 `ADR_PATTERN = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")` 4-digit pattern
- 本 ADR 编号 **0013**（下一可用），并在本 ADR 内说明原因

## 决策

**Mavis owner 决定**（per ADR-0008 自主决策授权）：

### 决策 1：roadmap 全对齐实际状态（8 节）

**对齐目标**：roadmap 与实际 commit/STATUS 状态 100% 一致，避免答辩时被「roadmap 写完成但实际没做」打脸。

| 节 | 改动 | 来源 |
|----|------|------|
| §1 总览 | M5 状态 ⚠️ 部分 → ⚠️ 部分→趋完成（5.5 ✅）| 本 session G4 落地 |
| §6 M5 | 5.5 状态 ⚠️ 部分 → ✅ 已做 | 本 session 6 必做落地 |
| §8.1 必修 P0 | 维持 ✅ 全数完成（凌晨冲刺 + G1/G2）| 既有 |
| §8.2 加分 P1 | 维持 ⚠️ P1-2/P1-3 ⬜ 待办 | 既有 |
| §8.2.1 增量 | 新增 G4 M5 5.5 文档沉淀收尾 | 本 session |
| §8.4 Demo 视频 | 维持 ✅ 但 v4 wallpaper 残留待 v6 | 既有 |
| §9 变更记录 | 新增 2026-06-07 14:26-15:00 + 15:30-17:00 两行 | 本 session + 14:26 session |
| §▶ 接手指引 | Mavis owner M5/MVP 收尾视角更新（新增交付物段 + 15:30 视角）| 本 session |

### 决策 2：5 层洋葱架构图（architecture-diagram.png + .svg）

**生成方法**：
1. **手写 SVG**（docs/deliverables/architecture-diagram.svg，1280×880 viewBox）：5 层水平堆叠 + 颜色梯度（L5 紫→L1 红）+ 跨层通信箭头（Command 下行 / Domain Event 上行）+ 依赖倒置标注
2. **playwright headless chromium 截图**（scripts/convert_svg_to_png.py，device_scale_factor=2 → 高清 PNG）→ 1.3 MB PNG

**图含要素**：
- **5 层水平堆叠**（从顶到底）：L5 Presentation / L4 API Gateway / L3 Application / L2 Domain / L1 Infrastructure
- **每层 6 模块**：L5 6 个 React 组件 / L4 6 个 FastAPI Router / L3 6 个 Service / L2 5 个聚合根 + TaskEngine / L1 5 类基础设施
- **跨层通信**：
  - 灰色实线箭头（Command 下行，HTTP/WS 请求）L5→L4→L3→L2
  - 青色虚线箭头（Domain Event 上行，Redis Pub/Sub）L1→L2
  - 依赖倒置标注：L1 实现 L2 接口
- **架构红线 AR-01~06** 速查框

**为何 inline SVG**：GitHub / 飞书 / VSCode preview 都直接渲染 SVG；PNG 高清截图适合答辩 PPT 插图。

### 决策 3：5 表 ER 图（er-diagram.png + .svg）

**5 主表 + 1 连接表**（per v4 PRD 简化）：
- **聚合根 5 个**：`agents` / `groups` / `sessions` / `messages` / `tasks`
- **连接表 1 个**：`group_members`（groups × agents 多对多）
- **自引用 2 个**：`messages.reply_to` / `tasks.parent_task_id`

**布局**（1600×1020 viewBox）：
- 左列：agents（顶）/ group_members（中，连接表）/ groups（底）
- 中列：sessions（中）+ tasks（底）
- 右列：messages（顶）
- 关系：实线=强制 FK / 虚线=可选 FK / 点线=自引用

**为何 SVG 手写**：Mermaid / dbdiagram.io 输出 PNG 是位图，文字不可缩放；SVG 矢量 + 可文字复制 + GitHub 友好。

### 决策 4：commands-reference.md 速查（37 REST + 11 WS）

**结构**（11 节）：
- §〇 基础约定（Base URL / 鉴权 / 错误响应）
- §一 REST 端点索引（按 11 域分组）
- §二 WS 事件协议（连接 + 信封 + 11 事件）
- §三 错误码字典（4 族：通用 / 业务 / Agent / MCP）
- §四 调用示例（cURL 4 例 + JS 1 例）
- §五 API 演化（v0 → v2.2 + 计划 v3）
- §六 关联文档（8 处跳转）

**关键约束**：
- 权威来源 04-commands v2.2（**不重复内容**）— 本文件 = 速查表，不复制契约
- 11 域分组：Setting / Agent / Group / Session&Message / Task / Inbox&Approval / Attachment / Usage / CLI Scan / MCP / Deploy
- 错误码 3 族：通用（13 个）+ 业务（19 个）+ MCP（13 个）
- 演化时间线：v0（5/20）→ v1（5/23）→ v2（6/3 MCP）→ v2.1（6/4 MCP F2）→ v2.2（6/7 BDD）→ v3（待定 P1-2/P1-3/P2）

### 决策 5：commit 拆分（6 commit 沿用 14:26 session 模式）

**6 commit 拆分**（per CLAUDE.md 行为准则 + 03-git PR-03）：

1. `docs(roadmap): 5.5 ✅ + G3/G4 增量 + §9 14:26/15:30 两行 + §▶接手指引更新`
2. `docs(deliverables): architecture-diagram 5 层洋葱 SVG + PNG`
3. `docs(deliverables): er-diagram 5 表 ER SVG + PNG`
4. `docs(deliverables): commands-reference v1.0 速查表 (37 REST + 11 WS)`
5. `docs(adr): 0013 mavis owner 创建 mavis-team 委派决策 (5.5 收尾 + 三大件可视化)`
6. `docs(worklog): 15:30 session 创建团队委派落档`

**附加文件**：
- `scripts/convert_svg_to_png.py`（新增工具脚本，commit 跟随第 2/3 commit）

**push 策略**：user 偏好（2026-06-07 落档 memory）—— **直接 push main**，不走 PR 流程。

## 影响

### 正面

- **M5 5.5 文档沉淀收尾** ⬜/⚠️ → **✅ 完成**（roadmap §六 5.5 状态更新）
- **课题 30% AI 协作能力**考察点「Spec、skill、rules 等协作规范」 + **课题 15% 代码理解度**考察点「架构选型解释」 双重满足
- **架构图可视化**：5 层依赖方向 + 跨层通信 + 红线速查 → **答辩 PPT 可直接截图插入**
- **ER 图可视化**：5 主表 + 1 连接 + 2 自引用 → **数据模型答辩可指图说话**
- **命令 reference 速查**：37 REST + 11 WS + 错误码字典 → **接手人 / 答辩时快速定位**
- **Mavis owner 委派模型**（per plan_ba86c4d0）→ **mavis-team 协作模式验证**

### 负面 / 后续 TODO

- **roadmap 全文 ~302 行**：本次 session 改 8 节，未做「roadmap 全文瘦身 + 单独维护一份 changelog」
- **架构图 / ER 图**：手写 SVG，复杂关系（如 N:N 桥接）需手工调整 — 未来 M 个位数增量可直接 patch
- **commands-reference.md**：v1.0 仅速查，**不替代** 04-commands 完整契约；文档双份维护成本低（仅错误码字典需同步）
- **本 ADR 不动 §2.6 MCP 冻结**——MCP 8 端点 PR-01 Review Approve 状态不变
- **playwright SVG→PNG 工具**：依赖 chromium 二进制，首次跑会触发 download（如未安装）

### 后续 roadmap

| 时机 | 任务 | 责任人 |
|------|------|------|
| M5 收束（6/9 答辩前）| 用本 session 3 截图插入答辩 PPT | Mavis owner |
| M6 答辩（6/10）| 跑 `scripts/check_docs.py` 0 错 + `scripts/check_worklog.py` 0 错 | docs-writer |
| v3 计划（待定）| P1-2 Usage 3 端点 + P1-3 CLI Scan 2 端点 + [P2] 会话置顶 + Deploy 3 端点 + 移动端 H5 路由 落 commands-reference v2.0 | backend + frontend |
| MVP 2.0（远期）| 50+ BDD 场景 + 300+ 单测 + 12+ E2E + CI gate 全绿 | 全员 |

## 替代方案

### 方案 B：架构图 / ER 图用 mermaid + dbdiagram.io 渲染

- **内容**：写 mermaid.js 代码 + dbdiagram.io DSL → 在线渲染 PNG
- **不选原因**：(a) 输出位图文字模糊；(b) 答辩断网/在线服务挂了无法重渲；(c) 字体/配色不可控
- **优势**：写起来快（5-10 行 DSL）

### 方案 C：commands-reference 用 Swagger 自动生成

- **内容**：FastAPI 启动时自动 OpenAPI 3.0 → Swagger UI 渲染
- **不选原因**：(a) Swagger 是给开发者交互用，不是速查表；(b) WS 事件不在 OpenAPI 范围；(c) 错误码字典需手工加注解
- **优势**：零维护（代码即文档）

### 方案 D：等下一会话再做 3 大件

- **内容**：本次 session 只写 worklog + roadmap，不动 deliverables
- **不选原因**：M5 5.5 已 ⚠️/⬜，课题 30% + 15% 考察点未满足；且 docs-writer 任务明确要求 5 必做
- **优势**：本次 session 工作量小

## 关联

- **上游决策**：
  - [ADR-0008 自主决策授权](0008-self-governance-authorization.md)（Mavis owner 有权写 ADR）
  - [ADR-0012 BDD spec precipitation](0012-bdd-spec-comprehensive-precipitation.md)（14:26 session 平行工作）
- **下游文档**：
  - [roadmap §一/§六/§8.1/§8.2/§8.2.1/§8.4/§九/§▶](../docs/plan/开发清单_roadmap.md)
  - [architecture-diagram.svg + .png](../docs/deliverables/architecture-diagram.svg)
  - [er-diagram.svg + .png](../docs/deliverables/er-diagram.svg)
  - [commands-reference.md](../docs/deliverables/commands-reference.md)
- **承接 worklog**：[worklogs/mavis/2026-06-07_创建团队委派.md](../worklogs/mavis/2026-06-07_创建团队委派.md)
- **plan_ba86c4d0 board**：[C:\Users\yhn\.mavis\plans\plan_ba86c4d0\board.md]

---

**状态追踪**：
- [x] 2026-06-07 15:30 - 决策起草（per plan_ba86c4d0 委派）
- [x] 2026-06-07 15:32 - roadmap §1/§6/§8.2.1/§九/§▶ 5 节对齐实际状态
- [x] 2026-06-07 15:38 - architecture-diagram.svg 手写（5 层 + 跨层通信 + 红线）
- [x] 2026-06-07 15:42 - playwright chromium 截图 → architecture-diagram.png（1.3 MB）
- [x] 2026-06-07 15:50 - er-diagram.svg 手写（5 主表 + 1 连接 + 2 自引用）
- [x] 2026-06-07 15:54 - playwright chromium 截图 → er-diagram.png（515 KB）
- [x] 2026-06-07 16:20 - commands-reference.md v1.0 写完（37 REST + 11 WS + 错误码字典 + 5 调用示例）
- [x] 2026-06-07 16:30 - ADR-0013 本文档落档（用 0013 编号，因 0012 已被 BDD session 占用）
- [x] 2026-06-07 16:40 - worklog mavis/2026-06-07_创建团队委派.md 落档
- [ ] 2026-06-07 16:50 - check_docs.py 0 错 + commit 6 拆分 + push main
- [ ] 2026-06-07 17:00 - 给 Mavis owner report commit hash
